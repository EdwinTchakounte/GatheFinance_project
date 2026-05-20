"""Tests du décaissement via Tara payout (J1).

Couvre :
  - `disburse_loan_via_tara` crée un Payment `en_attente` et appelle le provider mock
  - Le service est idempotent (pas de double payout)
  - Quand le webhook arrive, `_hook_decaissement` finalise le Loan
  - Erreur Tara non-retryable → Payment marqué rejeté, exception remontée
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.services import disburse_loan_via_tara
from apps_coop.payments.models import Payment
from apps_coop.payments.providers.base import ProviderError
from apps_coop.payments.services import handle_webhook_event


pytestmark = pytest.mark.django_db


def _build_approved_loan(member) -> Loan:
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("300000"),
        duree_mois=6,
        motif="Achat outillage",
        statut=LoanRequest.Statut.APPROUVEE,
        date_decision=timezone.now(),
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier="GF-CR-TARA-001",
        montant=Decimal("300000"),
        taux_interet=Decimal("0.12"),
        duree_mois=6,
        # Date placeholder — le hook la remettra à `today` après le webhook.
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=Decimal("336000"),
        solde_restant=Decimal("336000"),
        statut=Loan.Statut.ACTIF,
    )


class TestDisburseLoanViaTaraService:
    def test_creates_payment_in_pending_state_with_mock_reference(self, active_member, admin_user):
        loan = _build_approved_loan(active_member)
        payment = disburse_loan_via_tara(
            loan,
            agent=admin_user,
            recipient_phone="237699111222",
            network="MTN",
        )
        assert payment.type == Payment.Type.DECAISSEMENT
        assert payment.statut == Payment.Statut.EN_ATTENTE
        assert payment.source == Payment.Source.MOBILE_MONEY
        assert payment.provider_code == "tara"
        # Mock provider renvoie `MOCK-PAYOUT-<uuid>` quand TARA_API_KEY est vide.
        assert payment.reference_externe.startswith("MOCK-PAYOUT-")
        assert payment.gateway_initiated_at is not None

    def test_idempotent_pending_returns_existing(self, active_member, admin_user):
        loan = _build_approved_loan(active_member)
        p1 = disburse_loan_via_tara(loan, agent=admin_user, recipient_phone="237699111222", network="MTN")
        p2 = disburse_loan_via_tara(loan, agent=admin_user, recipient_phone="237699111222", network="MTN")
        assert p1.id == p2.id
        assert Payment.objects.filter(loan=loan, type=Payment.Type.DECAISSEMENT).count() == 1

    def test_webhook_confirmation_triggers_decaissement_hook(self, active_member, admin_user):
        loan = _build_approved_loan(active_member)
        payment = disburse_loan_via_tara(
            loan, agent=admin_user, recipient_phone="237699111222", network="MTN"
        )
        # On simule le webhook Tara `valide`
        handle_webhook_event(payment.idempotency_key, "valide", raw_payload={})
        loan.refresh_from_db()
        payment.refresh_from_db()
        assert payment.statut == Payment.Statut.VALIDE
        assert loan.statut == Loan.Statut.ACTIF
        assert loan.date_decaissement == date.today()


class TestDisburseLoanViaTaraErrors:
    def test_provider_error_marks_payment_rejected_and_reraises(
        self, active_member, admin_user, monkeypatch
    ):
        loan = _build_approved_loan(active_member)

        # Force le provider à lever une ProviderError non-retryable.
        from apps_coop.payments.providers import get_provider

        def boom(self, payment, *, recipient_phone, network):
            raise ProviderError("Tara KO", retryable=False)

        provider = get_provider("tara")
        monkeypatch.setattr(type(provider), "init_payout", boom)

        with pytest.raises(ProviderError):
            disburse_loan_via_tara(
                loan, agent=admin_user, recipient_phone="237699111222", network="MTN"
            )

        # On veut un Payment `rejete` traçant l'échec.
        rejected = Payment.objects.get(loan=loan, type=Payment.Type.DECAISSEMENT)
        assert rejected.statut == Payment.Statut.REJETE
        assert "Tara KO" in rejected.motif_rejet
