"""Tests LOT 3 (2026-07) — reconduction à terme, invalidation paiement,
suppression tracée de crédit."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.loans.deletion_services import (
    LoanDeletionError,
    delete_loan_request_traced,
)
from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.services import request_loan_renewal
from apps_coop.payments.invalidation_services import (
    PaymentInvalidationError,
    invalidate_payment,
)
from apps_coop.payments.models import Payment
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
)
from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


def _loan(member, *, solde="40000", butoir=None):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="x",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    loan = Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier=f"GF-CR-{member.id}",
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=Decimal(solde),
        solde_restant=Decimal(solde),
        statut=Loan.Statut.ACTIF,
        date_butoire=butoir,
    )
    LoanInstallment.objects.create(
        loan=loan,
        numero_echeance=1,
        date_echeance=date.today() + timedelta(days=30),
        montant_capital=Decimal(solde),
        montant_interets=Decimal("0"),
        montant_total=Decimal(solde),
        statut=LoanInstallment.Statut.A_VENIR,
    )
    return loan


class TestReconductionATerme:
    def test_blocked_before_term(self):
        m = MemberFactory()
        loan = _loan(m, butoir=date.today() + timedelta(days=20))
        with pytest.raises(ValueError, match="uniquement à l'échéance"):
            request_loan_renewal(loan, interets_au_comptant=False)

    def test_allowed_at_term(self):
        m = MemberFactory()
        loan = _loan(m, butoir=date.today() - timedelta(days=1))
        renewal = request_loan_renewal(loan, interets_au_comptant=False)
        assert renewal is not None


class TestPaymentInvalidation:
    def test_reverses_classic_deposit(self):
        m = MemberFactory()
        acc = ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("50000"), date_ouverture=date.today()
        )
        now = timezone.now()
        pay = Payment.objects.create(
            member=m,
            montant=Decimal("20000"),
            type=Payment.Type.EPARGNE_CLASSIQUE,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.VALIDE,
            date_versement=now,
            date_validation=now,
        )
        ClassicSavingsTransaction.objects.create(
            account=acc,
            payment=pay,
            type_op=ClassicSavingsTransaction.TypeOp.DEPOT,
            montant=Decimal("20000"),
            solde_apres=Decimal("50000"),
            date=now,
        )
        invalidate_payment(pay, actor=UserFactory())
        acc.refresh_from_db()
        pay.refresh_from_db()
        assert pay.statut == Payment.Statut.REJETE
        # 50 000 − 20 000 (annulation du dépôt) = 30 000.
        assert acc.solde == Decimal("30000.00")

    def test_reverses_repayment_reopens_loan(self):
        m = MemberFactory()
        loan = _loan(m, solde="0")  # soldé (remboursé)
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut"])
        inst = loan.installments.first()
        inst.montant_paye = Decimal("40000")
        inst.statut = LoanInstallment.Statut.PAYEE
        inst.save(update_fields=["montant_paye", "statut"])
        now = timezone.now()
        pay = Payment.objects.create(
            member=m,
            loan=loan,
            montant=Decimal("40000"),
            type=Payment.Type.REMBOURSEMENT,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.VALIDE,
            date_versement=now,
            date_validation=now,
        )
        from apps_coop.loans.models import LoanRepayment

        LoanRepayment.objects.create(
            installment=inst,
            payment=pay,
            montant_impute=Decimal("40000"),
            date=now,
        )
        invalidate_payment(pay, actor=UserFactory())
        loan.refresh_from_db()
        inst.refresh_from_db()
        assert loan.statut == Loan.Statut.ACTIF
        assert loan.solde_restant == Decimal("40000.00")
        assert inst.statut != LoanInstallment.Statut.PAYEE

    def test_idempotent_refuses_rejected(self):
        m = MemberFactory()
        pay = Payment.objects.create(
            member=m,
            montant=Decimal("1000"),
            type=Payment.Type.EPARGNE,
            source=Payment.Source.MANUEL,
            statut=Payment.Statut.REJETE,
            date_versement=timezone.now(),
        )
        with pytest.raises(PaymentInvalidationError):
            invalidate_payment(pay, actor=UserFactory())


class TestDeletionTraced:
    def test_delete_request_without_loan(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        m = MemberFactory()
        lr = LoanRequest.objects.create(
            member=m,
            montant_demande=Decimal("50000"),
            duree_mois=6,
            motif="erreur",
            statut=LoanRequest.Statut.EN_ATTENTE,
        )
        recap = delete_loan_request_traced(lr, actor=UserFactory(), motif="doublon")
        assert not LoanRequest.objects.filter(pk=lr.pk).exists()
        assert recap["loan_id"] is None
        trace = tmp_path / "audit" / "suppressions_credit.txt"
        assert trace.exists()
        assert "SUPPRESSION" in trace.read_text(encoding="utf-8")

    def test_delete_request_with_simple_loan(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        m = MemberFactory()
        loan = _loan(m, solde="40000")
        lr_id = loan.loan_request_id
        delete_loan_request_traced(loan.loan_request, actor=UserFactory())
        assert not Loan.objects.filter(pk=loan.pk).exists()
        assert not LoanRequest.objects.filter(pk=lr_id).exists()
