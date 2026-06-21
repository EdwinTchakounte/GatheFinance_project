"""Cycle contentieux 2026 — pénalité globale + saisie épargne automatique (R1).

Couvre :
  - Phase B : pénalité globale 50 % × solde_restant au franchissement de la
    date limite globale du crédit (= date de la dernière échéance)
  - Phase C : 30 jours après la pénalité globale → CONTENTIEUX → saisie épargne
  - R1 service : prélèvement épargne (cas suffisant + insuffisant)
  - Idempotence : ni la pénalité ni la saisie ne s'appliquent 2×
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AuditLog
from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.services import (
    apply_global_penalty,
    seize_member_savings_for_loan,
)
from apps_coop.loans.tasks import suivi_retards_quotidien
from apps_coop.savings.models import SavingsAccount, SavingsTransaction


pytestmark = pytest.mark.django_db(transaction=True)


def _build_loan(member, *, numero, solde_restant=Decimal("110000")):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=2,
        motif="Cycle contentieux test",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier=numero,
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        taux_penalite=Decimal("0.50"),
        duree_mois=2,
        date_decaissement=date.today() - timedelta(days=70),
        date_premiere_echeance=date.today() - timedelta(days=60),
        montant_total_du=Decimal("110000"),
        solde_restant=solde_restant,
        statut=Loan.Statut.ACTIF,
    )


def _build_installment(loan, *, days_late, numero=1):
    """Une seule échéance — sa date_echeance fait office de date_limite_globale."""
    return LoanInstallment.objects.create(
        loan=loan,
        numero_echeance=numero,
        date_echeance=date.today() - timedelta(days=days_late),
        montant_capital=Decimal("100000"),
        montant_interets=Decimal("10000"),
        montant_total=Decimal("110000"),
        montant_paye=Decimal("0"),
        statut=LoanInstallment.Statut.A_VENIR,
    )


# ---------------------------------------------------------------------------
# Phase B — Pénalité globale
# ---------------------------------------------------------------------------


class TestApplyGlobalPenalty:
    """Service ``apply_global_penalty`` (Phase B)."""

    def test_penalty_added_to_solde_restant(self, active_member):
        """Crédit à 110 000 → pénalité 55 000 → solde devient 165 000."""
        loan = _build_loan(active_member, numero="GLOBAL-1")
        penalite = apply_global_penalty(loan)
        assert penalite == Decimal("55000.00")
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("165000.00")
        assert loan.penalite_globale_appliquee_at is not None
        assert loan.statut == Loan.Statut.EN_RETARD

    def test_idempotent_second_call(self, active_member):
        loan = _build_loan(active_member, numero="GLOBAL-2")
        apply_global_penalty(loan)
        # 2ᵉ appel — pas de re-application.
        penalite2 = apply_global_penalty(loan)
        assert penalite2 == Decimal("0")
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("165000.00")

    def test_no_penalty_when_solde_zero(self, active_member):
        loan = _build_loan(active_member, numero="GLOBAL-3", solde_restant=Decimal("0"))
        penalite = apply_global_penalty(loan)
        assert penalite == Decimal("0")


# ---------------------------------------------------------------------------
# Phase C — Saisie épargne (R1)
# ---------------------------------------------------------------------------


class TestSeizeMemberSavings:
    """Service ``seize_member_savings_for_loan`` (R1)."""

    def test_savings_cover_full_amount(self, active_member):
        """Épargne 200 000 vs solde 165 000 → saisie 165 000, pas de poursuite."""
        loan = _build_loan(active_member, numero="R1-FULL")
        # On simule la post-pénalité globale.
        loan.solde_restant = Decimal("165000")
        loan.save(update_fields=["solde_restant"])

        SavingsAccount.objects.filter(member=active_member).update(solde=Decimal("200000"))

        result = seize_member_savings_for_loan(loan)
        assert result["saisie"] == Decimal("165000")
        assert result["epargne_apres"] == Decimal("35000")
        assert result["solde_restant_apres"] == Decimal("0")
        assert result["poursuite"] is False

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.CLOTURE
        assert loan.poursuite_judiciaire_at is None

    def test_savings_insufficient_triggers_pursuit(self, active_member):
        """Épargne 50 000 vs solde 165 000 → saisie 50 000 + flag poursuites."""
        loan = _build_loan(active_member, numero="R1-PARTIAL")
        loan.solde_restant = Decimal("165000")
        loan.save(update_fields=["solde_restant"])

        SavingsAccount.objects.filter(member=active_member).update(solde=Decimal("50000"))

        result = seize_member_savings_for_loan(loan)
        assert result["saisie"] == Decimal("50000")
        assert result["epargne_apres"] == Decimal("0")
        assert result["solde_restant_apres"] == Decimal("115000")
        assert result["poursuite"] is True

        loan.refresh_from_db()
        assert loan.poursuite_judiciaire_at is not None
        # Le crédit reste actif/en retard tant qu'il n'est pas soldé.

    def test_idempotent_second_call(self, active_member):
        loan = _build_loan(active_member, numero="R1-IDEMPOTENT")
        loan.solde_restant = Decimal("100000")
        loan.save(update_fields=["solde_restant"])
        SavingsAccount.objects.filter(member=active_member).update(solde=Decimal("100000"))

        first = seize_member_savings_for_loan(loan)
        assert first["saisie"] == Decimal("100000")

        # 2ᵉ appel — no_op.
        second = seize_member_savings_for_loan(loan)
        assert second["no_op"] is True
        # Le solde épargne ne bouge plus (vérif append-only ledger).
        assert SavingsTransaction.objects.filter(
            account__member=active_member,
            type_op=SavingsTransaction.TypeOp.RETRAIT_FORCE,
        ).count() == 1

    def test_writes_audit_savings_seized(self, active_member):
        loan = _build_loan(active_member, numero="R1-AUDIT")
        loan.solde_restant = Decimal("100000")
        loan.save(update_fields=["solde_restant"])
        SavingsAccount.objects.filter(member=active_member).update(solde=Decimal("80000"))

        seize_member_savings_for_loan(loan)

        audit = AuditLog.objects.filter(action="loan.savings_seized").first()
        assert audit is not None
        assert audit.details_json["saisie"] == "80000.00"
        assert audit.details_json["poursuite_engagee"] is True


# ---------------------------------------------------------------------------
# Cron complet — Phase B + Phase C bout-en-bout
# ---------------------------------------------------------------------------


class TestCronCycleEndToEnd:
    """Le cron quotidien doit appliquer Phase B (jour J = date limite) puis
    Phase C (J + 30) sans intervention humaine."""

    def test_phase_b_applies_global_penalty_at_date_limite(self, active_member):
        # Échéance unique à J-1 (= date limite globale franchie).
        loan = _build_loan(active_member, numero="CYCLE-B")
        _build_installment(loan, days_late=1)

        summary = suivi_retards_quotidien()

        assert summary["penalites_globales_appliquees"] == 1
        loan.refresh_from_db()
        assert loan.penalite_globale_appliquee_at is not None
        assert loan.solde_restant == Decimal("165000.00")

    def test_phase_c_triggers_contentieux_and_seizure_after_30_days(
        self, active_member
    ):
        """Pénalité posée il y a 31 j → cron bascule en CONTENTIEUX + saisie."""
        loan = _build_loan(active_member, numero="CYCLE-C")
        _build_installment(loan, days_late=31)
        # Force la pénalité globale comme si elle avait été posée 31 j plus tôt.
        loan.penalite_globale_appliquee_at = timezone.now() - timedelta(days=31)
        loan.penalite_globale_montant = Decimal("55000")
        loan.solde_restant = Decimal("165000")
        loan.statut = Loan.Statut.EN_RETARD
        loan.save(update_fields=[
            "penalite_globale_appliquee_at",
            "penalite_globale_montant",
            "solde_restant",
            "statut",
        ])
        SavingsAccount.objects.filter(member=active_member).update(solde=Decimal("200000"))

        summary = suivi_retards_quotidien()

        assert summary["contentieux_basculs"] == 1
        assert summary["contentieux_saisies"] == 1

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.CLOTURE
        assert loan.epargne_saisie_at is not None
        assert loan.epargne_saisie_montant == Decimal("165000.00")
        assert loan.solde_restant == Decimal("0")

    def test_phase_c_does_not_trigger_before_grace_period(self, active_member):
        """Pénalité posée il y a 10 j (< grâce 30 j) → pas de contentieux."""
        loan = _build_loan(active_member, numero="CYCLE-EARLY")
        _build_installment(loan, days_late=10)
        loan.penalite_globale_appliquee_at = timezone.now() - timedelta(days=10)
        loan.solde_restant = Decimal("165000")
        loan.save(update_fields=[
            "penalite_globale_appliquee_at", "solde_restant"
        ])
        SavingsAccount.objects.filter(member=active_member).update(solde=Decimal("200000"))

        summary = suivi_retards_quotidien()

        assert summary["contentieux_saisies"] == 0
        loan.refresh_from_db()
        assert loan.epargne_saisie_at is None
        assert loan.statut != Loan.Statut.CONTENTIEUX
