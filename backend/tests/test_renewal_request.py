"""Tests de la demande de reconduction côté membre (K1).

Couvre :
  - Service `request_loan_renewal` crée une `LoanRenewal(statut=demandee)`
  - Refus si statut Loan != actif/en_retard
  - Durée toujours forcée à +1 mois (Article 10), toute autre valeur ignorée
  - Idempotence : 2 appels successifs renvoient la même LoanRenewal
  - Endpoint HTTP returns 201 SANS frais (reconduction sans frais)
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps_coop.loans.models import Loan, LoanRenewal, LoanRequest
from apps_coop.loans.services import request_loan_renewal


pytestmark = pytest.mark.django_db


def _build_active_loan(member) -> Loan:
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("200000"),
        duree_mois=12,
        motif="Test renewal",
        statut=LoanRequest.Statut.APPROUVEE,
        date_decision=timezone.now(),
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier="GF-CR-RNW-001",
        montant=Decimal("200000"),
        taux_interet=Decimal("0.12"),
        duree_mois=12,
        date_decaissement=date.today() - timedelta(days=300),
        date_premiere_echeance=date.today() - timedelta(days=270),
        montant_total_du=Decimal("224000"),
        solde_restant=Decimal("80000"),
        statut=Loan.Statut.ACTIF,
    )


class TestRequestLoanRenewalService:
    def test_creates_renewal_for_active_loan(self, active_member):
        loan = _build_active_loan(active_member)
        renewal = request_loan_renewal(loan)
        assert renewal.statut == LoanRenewal.Statut.DEMANDEE
        # Article 10 : prorogation fixe de +1 mois, peu importe ce qui est demandé.
        assert renewal.nouvelle_duree_mois == 1
        assert renewal.loan_id == loan.id

    def test_duration_param_is_ignored_always_one_month(self, active_member):
        """Toute durée passée est écrasée par +1 mois (Article 10)."""
        loan = _build_active_loan(active_member)
        renewal = request_loan_renewal(loan, nouvelle_duree_mois=12)
        assert renewal.nouvelle_duree_mois == 1

    def test_rejects_closed_loan(self, active_member):
        loan = _build_active_loan(active_member)
        loan.statut = Loan.Statut.CLOTURE
        loan.save()
        with pytest.raises(ValueError, match="(?i)cloture"):
            request_loan_renewal(loan, nouvelle_duree_mois=6)

    def test_defaults_to_one_month_when_duration_absent(self, active_member):
        """Article 10 — délai supplémentaire d'un mois fixe."""
        loan = _build_active_loan(active_member)
        renewal = request_loan_renewal(loan)
        assert renewal.nouvelle_duree_mois == 1

    def test_records_interets_au_comptant_flag(self, active_member):
        """Article 11 — choix du membre entre taux 10 % et 15 %."""
        loan = _build_active_loan(active_member)
        renewal = request_loan_renewal(loan, interets_au_comptant=True)
        assert renewal.interets_au_comptant is True

    def test_idempotent_double_request_returns_same_renewal(self, active_member):
        loan = _build_active_loan(active_member)
        r1 = request_loan_renewal(loan, nouvelle_duree_mois=6)
        r2 = request_loan_renewal(loan, nouvelle_duree_mois=12)  # même renewal renvoyée
        assert r1.id == r2.id
        assert LoanRenewal.objects.filter(loan=loan).count() == 1


class TestRenewalEndpoint:
    def test_endpoint_returns_201_without_fee(self, client, active_member):
        loan = _build_active_loan(active_member)
        client.force_login(active_member.user)
        resp = client.post(
            f"/api/v1/loans/{loan.id}/renewal/",
            data={"nouvelle_duree_mois": 6},
            content_type="application/json",
        )
        assert resp.status_code == 201, resp.content
        body = resp.json()
        assert body["renewal"]["statut"] == "demandee"
        assert body["renewal"]["loan_id"] == loan.id
        # +1 mois forcé, peu importe la durée demandée.
        assert body["renewal"]["nouvelle_duree_mois"] == 1
        # Reconduction sans frais : aucune clé `frais_a_payer` dans la réponse.
        assert "frais_a_payer" not in body

    def test_endpoint_404_on_foreign_loan(self, client, active_member):
        # Crée un Loan qui n'appartient PAS à active_member
        from tests.factories import MemberFactory
        other = MemberFactory()
        loan = _build_active_loan(other)
        client.force_login(active_member.user)
        resp = client.post(
            f"/api/v1/loans/{loan.id}/renewal/",
            data={"nouvelle_duree_mois": 6},
            content_type="application/json",
        )
        assert resp.status_code == 404
