"""Tests des hooks paiement câblés.

  - _hook_carnet_fees          → crée BookletOrder, idempotent
  - _hook_decaissement         → bascule Loan.statut = actif + date_decaissement

NB : la reconduction est désormais SANS frais — il n'existe plus de hook
`_hook_loan_renewal_fees` (cf. test_renewal_decision.py).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.loans.models import Loan, LoanInstallment, LoanRenewal, LoanRequest
from apps_coop.members.models import BookletOrder
from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event


pytestmark = pytest.mark.django_db


def _make_payment(member, type_, *, montant=Decimal("1000"), loan=None) -> Payment:
    return Payment.objects.create(
        member=member,
        montant=montant,
        type=type_,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.EN_ATTENTE,
        provider_code="tara",
        date_versement=timezone.now(),
        loan=loan,
    )


# -- I1 — frais_carnet ------------------------------------------------------


class TestCarnetFeesHook:
    def test_creates_booklet_order_on_webhook_validation(self, active_member):
        payment = _make_payment(active_member, Payment.Type.FRAIS_CARNET, montant=Decimal("1000"))
        handle_webhook_event(payment.idempotency_key, "valide", raw_payload={})
        order = BookletOrder.objects.get(payment=payment)
        assert order.member == active_member
        assert order.statut == BookletOrder.Statut.PAYEE
        assert order.date_impression is None

    def test_replay_does_not_duplicate_order_or_email(self, active_member):
        payment = _make_payment(active_member, Payment.Type.FRAIS_CARNET, montant=Decimal("1000"))
        handle_webhook_event(payment.idempotency_key, "valide", raw_payload={})
        # Tara rejoue → no-op
        handle_webhook_event(payment.idempotency_key, "valide", raw_payload={})
        assert BookletOrder.objects.filter(payment=payment).count() == 1


# -- helper partagé : crédit actif (+ renewal pour les besoins du test) ------


def _seed_active_loan_with_renewal(member) -> tuple[Loan, LoanRenewal]:
    """Crée un Loan actif + une LoanRenewal `demandee` sans paiement de frais."""
    loan_request = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("200000"),
        duree_mois=6,
        motif="Test",
        statut=LoanRequest.Statut.APPROUVEE,
        date_decision=timezone.now(),
    )
    loan = Loan.objects.create(
        member=member,
        loan_request=loan_request,
        numero_dossier="GF-CR-TEST-001",
        montant=Decimal("200000"),
        taux_interet=Decimal("0.12"),
        duree_mois=6,
        date_decaissement=date.today() - timedelta(days=180),
        date_premiere_echeance=date.today() - timedelta(days=150),
        montant_total_du=Decimal("224000"),
        solde_restant=Decimal("50000"),
        statut=Loan.Statut.ACTIF,
    )
    renewal = LoanRenewal.objects.create(loan=loan, nouvelle_duree_mois=6)
    return loan, renewal


# -- I3 — decaissement ------------------------------------------------------


class TestDecaissementHook:
    def test_loan_is_marked_actif_and_date_decaissement_set(self, active_member):
        loan, _ = _seed_active_loan_with_renewal(active_member)
        # Pour le test on remet le loan en pseudo "en attente de décaissement".
        loan.statut = Loan.Statut.ACTIF  # reste actif, mais date_decaissement à override
        loan.date_decaissement = date.today() - timedelta(days=365)  # vieille date
        loan.save()
        payment = _make_payment(
            active_member, Payment.Type.DECAISSEMENT, montant=Decimal("200000"), loan=loan
        )
        handle_webhook_event(payment.idempotency_key, "valide", raw_payload={})
        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.ACTIF
        assert loan.date_decaissement == date.today()

    def test_missing_loan_id_logs_error_no_crash(self, active_member, caplog):
        payment = _make_payment(active_member, Payment.Type.DECAISSEMENT, montant=Decimal("50000"))
        with caplog.at_level("ERROR"):
            handle_webhook_event(payment.idempotency_key, "valide", raw_payload={})
        assert any("decaissement" in r.message.lower() or "loan_id" in r.message for r in caplog.records)
