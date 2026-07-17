"""Transfert — rembourser un crédit depuis l'épargne (G6, refonte 2026-07).

Puise dans l'épargne classique retirable puis la collecte, sans Mobile Money.
Le placement / l'épargne gelée ne sont jamais ponctionnés.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.transfer_services import (
    TransferError,
    repay_loan_from_savings,
)
from apps_coop.payments.models import Payment
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _classic(member, solde):
    return ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(solde), date_ouverture=date.today()
    )


def _loan(member, *, montant="100000", solde="80000"):
    lr = LoanRequest.objects.create(
        member=member, montant_demande=Decimal(montant), duree_mois=6,
        motif="x", statut=LoanRequest.Statut.APPROUVEE,
    )
    loan = Loan.objects.create(
        member=member, loan_request=lr, numero_dossier=f"GF-CR-{member.id}",
        montant=Decimal(montant), taux_interet=Decimal("0.10"), duree_mois=6,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=Decimal(montant), solde_restant=Decimal(solde),
        statut=Loan.Statut.ACTIF,
    )
    LoanInstallment.objects.create(
        loan=loan, numero_echeance=1,
        date_echeance=date.today() + timedelta(days=30),
        montant_capital=Decimal(solde), montant_interets=Decimal("0"),
        montant_total=Decimal(solde), statut=LoanInstallment.Statut.A_VENIR,
    )
    return loan


class TestService:
    def test_rembourse_depuis_epargne_classique(self):
        m = MemberFactory()
        acc = _classic(m, "30000")
        loan = _loan(m, solde="80000")

        payment = repay_loan_from_savings(loan, Decimal("20000"))

        assert payment.type == Payment.Type.REMBOURSEMENT
        assert payment.source == Payment.Source.DEDUCTION_EPARGNE
        assert payment.statut == Payment.Statut.VALIDE
        acc.refresh_from_db()
        assert acc.solde == Decimal("10000.00")
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("60000.00")

    def test_puise_classique_puis_collecte(self):
        m = MemberFactory()
        acc = _classic(m, "5000")
        # MemberFactory crée le compte collecte ; on lui met un solde.
        coll = SavingsAccount.objects.get(member=m)
        coll.solde = Decimal("10000")
        coll.save(update_fields=["solde"])
        loan = _loan(m, solde="80000")

        repay_loan_from_savings(loan, Decimal("12000"))

        acc.refresh_from_db()
        coll.refresh_from_db()
        # 5 000 classique + 7 000 collecte = 12 000
        assert acc.solde == Decimal("0.00")
        assert coll.solde == Decimal("3000.00")
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("68000.00")

    def test_refuse_si_insuffisant(self):
        m = MemberFactory()
        _classic(m, "1000")
        loan = _loan(m, solde="80000")
        with pytest.raises(TransferError):
            repay_loan_from_savings(loan, Decimal("50000"))

    def test_ne_depasse_pas_le_solde_restant(self):
        m = MemberFactory()
        acc = _classic(m, "100000")
        loan = _loan(m, solde="30000")
        payment = repay_loan_from_savings(loan, Decimal("50000"))
        # plafonné au solde restant (30 000)
        assert payment.montant == Decimal("30000.00")
        acc.refresh_from_db()
        assert acc.solde == Decimal("70000.00")
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("0.00")


class TestEndpoints:
    def test_available_endpoint(self):
        m = MemberFactory()
        _classic(m, "25000")
        r = _api(m.user).get("/api/v1/loans/transfer/available/")
        assert r.status_code == 200
        assert Decimal(r.data["classic"]) == Decimal("25000")

    def test_repay_endpoint(self):
        m = MemberFactory()
        _classic(m, "40000")
        loan = _loan(m, solde="80000")
        r = _api(m.user).post(
            f"/api/v1/loans/me/loans/{loan.id}/repay-from-savings/",
            {"montant": "15000"},
        )
        assert r.status_code == 200
        assert Decimal(r.data["solde_restant"]) == Decimal("65000")

    def test_repay_autre_membre_404(self):
        m = MemberFactory()
        other = MemberFactory()
        _classic(other, "40000")
        loan = _loan(other, solde="80000")
        r = _api(m.user).post(
            f"/api/v1/loans/me/loans/{loan.id}/repay-from-savings/",
            {"montant": "1000"},
        )
        assert r.status_code == 404
