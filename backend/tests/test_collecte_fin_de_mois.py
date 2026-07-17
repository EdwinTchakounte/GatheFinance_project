"""LOT 4 (refonte 2026) — Cron mensuel de clôture des comptes de collecte
journalière (``collecte_fin_de_mois``).

Couvre :
  - Mode CASH : commission 1% + restitution au membre, solde → 0
  - Mode EPARGNE : commission 1% + bascule vers ClassicSavingsAccount
  - Création à la volée de ClassicSavingsAccount si inexistant
  - Idempotence par mois calendaire (pas 2× COMMISSION)
  - Kill-switch ``collecte.monthly.enabled``
  - Taux configurable ``collecte.monthly.commission_rate``
  - Skip des comptes solde = 0 et membres suspendus
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    SavingsAccount,
    SavingsTransaction,
)
from apps_coop.savings.tasks import collecte_fin_de_mois


pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_collecte_balance(member, montant: Decimal):
    acc = member.savings_account
    acc.solde = montant
    acc.save(update_fields=["solde"])
    return acc


def _set_preference(member, preference):
    acc = member.savings_account
    acc.end_of_month_preference = preference
    acc.save(update_fields=["end_of_month_preference"])


# ---------------------------------------------------------------------------
# Mode CASH (défaut)
# ---------------------------------------------------------------------------


class TestModeCash:
    """Préférence CASH : commission prélevée + restitution attendue côté membre.

    Note refonte 2026 : le défaut est désormais 0 % (restitution intégrale).
    Ces tests forcent 1 % explicitement pour vérifier que la mécanique de
    commission fonctionne quand l'admin l'active.
    """

    def test_commission_and_restitution(self, active_member):
        # 100 000 FCFA collectés au mois. Commission 1% = 1 000.
        # Restituable = 99 000. Solde après = 0.
        AppSetting.objects.update_or_create(
            cle="collecte.monthly.commission_rate", defaults={"valeur": "0.01"}
        )
        _set_collecte_balance(active_member, Decimal("100000"))

        summary = collecte_fin_de_mois()

        acc = active_member.savings_account
        acc.refresh_from_db()
        assert summary["comptes_traites"] == 1
        assert summary["erreurs"] == 0
        assert summary["total_commission"] == "1000.00"
        assert summary["total_restitue_cash"] == "99000.00"
        assert acc.solde == Decimal("0")

        # Le ledger comporte 2 lignes : COMMISSION + RESTITUTION_CASH.
        commission_tx = SavingsTransaction.objects.get(
            account=acc, type_op=SavingsTransaction.TypeOp.COMMISSION
        )
        assert commission_tx.montant == Decimal("1000.00")
        assert commission_tx.solde_apres == Decimal("99000.00")

        restitution_tx = SavingsTransaction.objects.get(
            account=acc, type_op=SavingsTransaction.TypeOp.RESTITUTION_CASH
        )
        assert restitution_tx.montant == Decimal("99000.00")
        assert restitution_tx.solde_apres == Decimal("0")


# ---------------------------------------------------------------------------
# Mode EPARGNE — bascule automatique
# ---------------------------------------------------------------------------


class TestModeEpargne:
    """Préférence EPARGNE : commission + bascule vers ClassicSavingsAccount."""

    def test_creates_classic_account_on_the_fly(self, active_member):
        AppSetting.objects.update_or_create(
            cle="collecte.monthly.commission_rate", defaults={"valeur": "0.01"}
        )
        _set_collecte_balance(active_member, Decimal("50000"))
        _set_preference(
            active_member, SavingsAccount.EndOfMonthPreference.EPARGNE
        )
        # Pas de compte épargne classique avant.
        assert not ClassicSavingsAccount.objects.filter(member=active_member).exists()

        summary = collecte_fin_de_mois()

        assert summary["total_bascule_epargne"] == "49500.00"  # 50000 - 500 (1%)
        # Le compte épargne classique a été créé avec le solde.
        classic = ClassicSavingsAccount.objects.get(member=active_member)
        assert classic.solde == Decimal("49500.00")
        # Le compte collecte est vide.
        acc = active_member.savings_account
        acc.refresh_from_db()
        assert acc.solde == Decimal("0")

    def test_credits_existing_classic_account(self, active_member):
        from datetime import date

        AppSetting.objects.update_or_create(
            cle="collecte.monthly.commission_rate", defaults={"valeur": "0.01"}
        )
        # Compte épargne classique pré-existant avec un solde.
        classic = ClassicSavingsAccount.objects.create(
            member=active_member,
            solde=Decimal("10000"),
            date_ouverture=date.today(),
        )
        _set_collecte_balance(active_member, Decimal("20000"))
        _set_preference(
            active_member, SavingsAccount.EndOfMonthPreference.EPARGNE
        )

        collecte_fin_de_mois()

        classic.refresh_from_db()
        # 10 000 + (20 000 - 200 commission) = 29 800.
        assert classic.solde == Decimal("29800.00")

        # Une ligne BASCULE_COLLECTE sur le ledger épargne classique (origine
        # explicite : virement depuis la collecte, pas un dépôt MoMo — G3 2026).
        classic_dep = ClassicSavingsTransaction.objects.get(
            account=classic,
            type_op=ClassicSavingsTransaction.TypeOp.BASCULE_COLLECTE,
        )
        assert classic_dep.montant == Decimal("19800.00")
        assert classic_dep.solde_apres == Decimal("29800.00")

    def test_writes_bascule_epargne_on_collecte_ledger(self, active_member):
        AppSetting.objects.update_or_create(
            cle="collecte.monthly.commission_rate", defaults={"valeur": "0.01"}
        )
        _set_collecte_balance(active_member, Decimal("10000"))
        _set_preference(
            active_member, SavingsAccount.EndOfMonthPreference.EPARGNE
        )

        collecte_fin_de_mois()

        bascule = SavingsTransaction.objects.get(
            account=active_member.savings_account,
            type_op=SavingsTransaction.TypeOp.BASCULE_EPARGNE,
        )
        assert bascule.montant == Decimal("9900.00")
        assert bascule.solde_apres == Decimal("0")


# ---------------------------------------------------------------------------
# Idempotence — pas 2× COMMISSION pour le même mois
# ---------------------------------------------------------------------------


class TestIdempotence:
    def test_second_run_same_month_skips(self, active_member):
        _set_collecte_balance(active_member, Decimal("100000"))
        collecte_fin_de_mois()

        # Recharge la collecte (simule un dépôt après clôture).
        _set_collecte_balance(active_member, Decimal("100000"))
        summary2 = collecte_fin_de_mois()

        # Le 2ᵉ passage doit IGNORER ce compte (commission déjà ce mois).
        assert summary2["comptes_traites"] == 0
        assert summary2["comptes_ignores"] == 1
        # Solde reste à 100 000 (non re-prélevé).
        acc = active_member.savings_account
        acc.refresh_from_db()
        assert acc.solde == Decimal("100000")


# ---------------------------------------------------------------------------
# Kill-switch + taux configurable
# ---------------------------------------------------------------------------


class TestKillSwitch:
    def test_disabled_returns_skipped(self, active_member):
        AppSetting.objects.update_or_create(
            cle="collecte.monthly.enabled", defaults={"valeur": "false"}
        )
        _set_collecte_balance(active_member, Decimal("100000"))
        summary = collecte_fin_de_mois()
        assert "skipped_reason" in summary
        # Aucune écriture ledger.
        assert not SavingsTransaction.objects.filter(
            account=active_member.savings_account,
            type_op=SavingsTransaction.TypeOp.COMMISSION,
        ).exists()

    def test_custom_commission_rate(self, active_member):
        # Admin passe la commission à 2%.
        AppSetting.objects.update_or_create(
            cle="collecte.monthly.commission_rate", defaults={"valeur": "0.02"}
        )
        _set_collecte_balance(active_member, Decimal("100000"))
        summary = collecte_fin_de_mois()
        # 100 000 × 2% = 2 000 commission. Restituable = 98 000.
        assert summary["total_commission"] == "2000.00"
        assert summary["total_restitue_cash"] == "98000.00"

    def test_default_one_percent_commission(self, active_member):
        """Refonte 2026 — défaut 1 % : la coopérative prélève la commission.

        Vérifie que sans AppSetting explicite, le fallback applique 1 % du
        solde (règle métier maintenue). L'admin peut ramener à 0 ou modifier
        depuis Paramètres 2026.
        """
        # Pas d'AppSetting → fallback au défaut "0.01".
        AppSetting.objects.filter(cle="collecte.monthly.commission_rate").delete()
        _set_collecte_balance(active_member, Decimal("100000"))
        summary = collecte_fin_de_mois()
        # 100 000 × 1 % = 1 000 commission. Restituable = 99 000.
        assert summary["total_commission"] == "1000.00"
        assert summary["total_restitue_cash"] == "99000.00"
        # Le solde du compte collecte est ramené à 0.
        acc = active_member.savings_account
        acc.refresh_from_db()
        assert acc.solde == Decimal("0")

    def test_admin_can_disable_commission(self, active_member):
        """Admin peut ramener la commission à 0 — restitution intégrale."""
        AppSetting.objects.update_or_create(
            cle="collecte.monthly.commission_rate", defaults={"valeur": "0"}
        )
        _set_collecte_balance(active_member, Decimal("100000"))
        summary = collecte_fin_de_mois()
        assert summary["total_commission"] == "0.00"
        assert summary["total_restitue_cash"] == "100000.00"


# ---------------------------------------------------------------------------
# Cas limites
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_skips_account_with_zero_balance(self, active_member):
        _set_collecte_balance(active_member, Decimal("0"))
        summary = collecte_fin_de_mois()
        assert summary["comptes_traites"] == 0
        assert summary["comptes_ignores"] == 1

    def test_skips_suspended_member(self, suspended_member):
        _set_collecte_balance(suspended_member, Decimal("50000"))
        summary = collecte_fin_de_mois()
        # Membre suspendu → pas dans la queryset.
        assert summary["comptes_traites"] == 0
        # Solde inchangé.
        acc = suspended_member.savings_account
        acc.refresh_from_db()
        assert acc.solde == Decimal("50000")

    def test_writes_audit_on_each_account(self, active_member):
        AppSetting.objects.update_or_create(
            cle="collecte.monthly.commission_rate", defaults={"valeur": "0.01"}
        )
        _set_collecte_balance(active_member, Decimal("100000"))
        collecte_fin_de_mois()
        audit = AuditLog.objects.filter(
            action="collecte.monthly_closed",
            entite_type="SavingsAccount",
        ).first()
        assert audit is not None
        assert audit.details_json["commission"] == "1000.00"
        assert audit.details_json["preference"] == "cash"

    def test_summary_audit_at_end(self, active_member):
        _set_collecte_balance(active_member, Decimal("100000"))
        collecte_fin_de_mois()
        audit = AuditLog.objects.filter(
            action="cron.collecte_fin_de_mois.run"
        ).first()
        assert audit is not None
        assert audit.details_json["comptes_traites"] == 1
