"""Cron quotidien des retards de crédit (Articles 12-13)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.tasks import (
    CONTENTIEUX_THRESHOLD_DAYS,
    LATE_PENALTY_RATE,
    _compute_penalty,
    suivi_retards_quotidien,
)


pytestmark = pytest.mark.django_db(transaction=True)


def _build_loan(member, **overrides):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test late payment",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier=overrides.get("numero", "GF-CR-LATE-001"),
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=120),
        date_premiere_echeance=date.today() - timedelta(days=60),
        montant_total_du=Decimal("110000"),
        solde_restant=Decimal("110000"),
        statut=overrides.get("statut", Loan.Statut.ACTIF),
    )


def _build_installment(loan, *, days_late, statut=LoanInstallment.Statut.A_VENIR, montant_paye=Decimal("0"), numero=1):
    return LoanInstallment.objects.create(
        loan=loan,
        numero_echeance=numero,
        date_echeance=date.today() - timedelta(days=days_late),
        montant_capital=Decimal("33334"),
        montant_interets=Decimal("3333"),
        montant_total=Decimal("36667"),
        montant_paye=montant_paye,
        statut=statut,
    )


class TestPenaltyComputation:
    """Article 12 — 50 % des intérêts proratisés sur la somme manquante."""

    def test_full_amount_due_full_penalty(self):
        # Échéance 30 000 (20 000 capital + 10 000 intérêts), rien payé.
        # Pénalité = 50 % × 10 000 = 5 000
        p = _compute_penalty(Decimal("10000"), Decimal("30000"), Decimal("0"))
        assert p == Decimal("5000.00")

    def test_half_paid_half_penalty(self):
        # Échéance 30 000, 15 000 payés → reste 50 % → 50 % × 50 % × 10 000 = 2 500.
        p = _compute_penalty(Decimal("10000"), Decimal("30000"), Decimal("15000"))
        assert p == Decimal("2500.00")

    def test_fully_paid_no_penalty(self):
        p = _compute_penalty(Decimal("10000"), Decimal("30000"), Decimal("30000"))
        assert p == Decimal("0.00")

    def test_rate_constant(self):
        assert LATE_PENALTY_RATE == Decimal("0.50")


class TestSuiviRetardsCron:
    def test_marks_installment_en_retard_and_applies_penalty(self, active_member):
        loan = _build_loan(active_member)
        inst = _build_installment(loan, days_late=10)

        summary = suivi_retards_quotidien()

        inst.refresh_from_db()
        assert inst.statut == LoanInstallment.Statut.EN_RETARD
        assert inst.montant_penalite == Decimal("1666.50")  # 3333 × 50 % = 1666.5
        assert inst.penalite_appliquee_at is not None
        assert summary["passees_en_retard"] == 1
        assert summary["penalites_appliquees"] == 1

    def test_idempotent_does_not_double_apply_penalty(self, active_member):
        loan = _build_loan(active_member)
        inst = _build_installment(loan, days_late=10)

        suivi_retards_quotidien()
        first_penalty = LoanInstallment.objects.get(pk=inst.pk).montant_penalite
        first_at = LoanInstallment.objects.get(pk=inst.pk).penalite_appliquee_at

        summary2 = suivi_retards_quotidien()
        inst.refresh_from_db()

        # La pénalité n'a pas changé, le timestamp non plus.
        assert inst.montant_penalite == first_penalty
        assert inst.penalite_appliquee_at == first_at
        # Le 2e run ne ré-applique pas de pénalité (déjà en_retard).
        assert summary2["passees_en_retard"] == 0

    def test_loan_passes_en_retard_when_installment_late(self, active_member):
        loan = _build_loan(active_member)
        _build_installment(loan, days_late=5)

        suivi_retards_quotidien()

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.EN_RETARD

    def test_loan_passes_contentieux_after_threshold(self, active_member):
        loan = _build_loan(active_member, numero="GF-CR-LATE-CTX")
        _build_installment(loan, days_late=CONTENTIEUX_THRESHOLD_DAYS + 5)

        suivi_retards_quotidien()

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.CONTENTIEUX

    def test_skips_paid_installment(self, active_member):
        loan = _build_loan(active_member, numero="GF-CR-LATE-PAID")
        inst = _build_installment(
            loan,
            days_late=20,
            statut=LoanInstallment.Statut.PAYEE,
            montant_paye=Decimal("36667"),
        )

        suivi_retards_quotidien()

        inst.refresh_from_db()
        # Pas touché : la cron n'examine que A_VENIR ou PARTIELLE.
        assert inst.statut == LoanInstallment.Statut.PAYEE
        assert inst.montant_penalite == Decimal("0")

    def test_skips_cloture_loan(self, active_member):
        loan = _build_loan(
            active_member,
            numero="GF-CR-LATE-CLO",
            statut=Loan.Statut.CLOTURE,
        )
        _build_installment(loan, days_late=10)

        suivi_retards_quotidien()

        loan.refresh_from_db()
        # Un Loan clôturé reste clôturé même si une échéance traîne.
        assert loan.statut == Loan.Statut.CLOTURE
