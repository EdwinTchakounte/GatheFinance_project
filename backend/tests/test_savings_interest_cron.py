"""Cron mensuel des intérêts d'épargne (Règlement, Article 4).

⚠️ LEGACY 2025 — Depuis la refonte 2026, le cron est désactivé par défaut via
``savings.monthly_interest.enabled`` (LOT 3). Les tests historiques activent
explicitement le kill-switch pour préserver la couverture du comportement
legacy ; le LOT 4 remplacera le cron par ``collecte_fin_de_mois`` (commission
1% prélevée vs intérêt 1% crédité).
"""
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.savings.cutoff import MIN_BALANCE_FOR_INTEREST, MONTHLY_INTEREST_RATE
from apps_coop.savings.models import SavingsAccount, SavingsTransaction
from apps_coop.savings.tasks import crediter_interets_mensuels


@pytest.fixture
def enable_legacy_interest_cron():
    """LOT 3 — active le cron legacy d'intérêts mensuels.

    Le kill-switch ``savings.monthly_interest.enabled`` est ``false`` par
    défaut depuis la refonte 2026. Les tests qui vérifient le comportement
    legacy 2025 (crédit 1%/mois) doivent l'activer explicitement.
    """
    AppSetting.objects.update_or_create(
        cle="savings.monthly_interest.enabled",
        defaults={"valeur": "true"},
    )


@pytest.mark.django_db(transaction=True)
class TestCreditMonthlyInterest:
    def test_credits_1pct_on_active_account(self, active_member, enable_legacy_interest_cron):
        acc = active_member.savings_account
        acc.solde = Decimal("100000")
        acc.save(update_fields=["solde"])

        summary = crediter_interets_mensuels()

        acc.refresh_from_db()
        assert summary["comptes_traites"] == 1
        assert summary["erreurs"] == 0
        assert acc.solde == Decimal("101000.00")

        tx = SavingsTransaction.objects.get(
            account=acc, type_op=SavingsTransaction.TypeOp.INTERET
        )
        assert tx.montant == Decimal("1000.00")
        assert tx.payment is None
        assert tx.solde_apres == Decimal("101000.00")

    def test_idempotent_same_month_no_double_credit(self, active_member, enable_legacy_interest_cron):
        acc = active_member.savings_account
        acc.solde = Decimal("100000")
        acc.save(update_fields=["solde"])

        crediter_interets_mensuels()
        summary2 = crediter_interets_mensuels()

        acc.refresh_from_db()
        assert summary2["comptes_traites"] == 0
        assert summary2["comptes_ignores"] == 1
        # Solde inchangé après le 2e passage.
        assert acc.solde == Decimal("101000.00")
        assert SavingsTransaction.objects.filter(
            account=acc, type_op=SavingsTransaction.TypeOp.INTERET
        ).count() == 1

    def test_skips_account_below_min_balance(self, active_member, enable_legacy_interest_cron):
        acc = active_member.savings_account
        acc.solde = MIN_BALANCE_FOR_INTEREST - Decimal("1")  # 99 XAF
        acc.save(update_fields=["solde"])

        summary = crediter_interets_mensuels()

        acc.refresh_from_db()
        assert summary["comptes_traites"] == 0
        assert summary["comptes_ignores"] == 1
        assert acc.solde == Decimal("99")  # inchangé
        assert not SavingsTransaction.objects.filter(
            account=acc, type_op=SavingsTransaction.TypeOp.INTERET
        ).exists()

    def test_skips_suspended_member(self, suspended_member, enable_legacy_interest_cron):
        # Un membre suspendu a un SavingsAccount avec solde 0 par défaut.
        # On le passe à 100000 pour vérifier que le cron skip quand même.
        acc = suspended_member.savings_account
        acc.solde = Decimal("100000")
        acc.save(update_fields=["solde"])

        summary = crediter_interets_mensuels()

        acc.refresh_from_db()
        # Le compte d'un membre suspendu n'est même pas scanné → ni traité ni ignoré.
        assert summary["comptes_traites"] == 0
        assert acc.solde == Decimal("100000")  # inchangé

    def test_rate_constant_matches_regulation(self):
        # Garde-fou : si quelqu'un change la constante, le test rouge.
        assert MONTHLY_INTEREST_RATE == Decimal("0.01")


# ---------------------------------------------------------------------------
# LOT 3 (refonte 2026) — Kill-switch ``savings.monthly_interest.enabled``
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestKillSwitchRefonte2026:
    """Le cron 2025 doit être désactivé par défaut depuis la refonte 2026."""

    def test_disabled_by_default_returns_skipped_summary(self, active_member):
        # Aucun AppSetting posé → défaut "false" via get_str_setting.
        acc = active_member.savings_account
        acc.solde = Decimal("100000")
        acc.save(update_fields=["solde"])

        summary = crediter_interets_mensuels()

        # Le cron a tourné à blanc.
        assert "skipped_reason" in summary
        assert "refonte 2026" in summary["skipped_reason"]
        # Solde inchangé — pas d'intérêt crédité.
        acc.refresh_from_db()
        assert acc.solde == Decimal("100000")
        assert not SavingsTransaction.objects.filter(
            account=acc, type_op=SavingsTransaction.TypeOp.INTERET
        ).exists()

    def test_explicit_false_also_skips(self, active_member):
        AppSetting.objects.update_or_create(
            cle="savings.monthly_interest.enabled",
            defaults={"valeur": "false"},
        )
        acc = active_member.savings_account
        acc.solde = Decimal("100000")
        acc.save(update_fields=["solde"])

        summary = crediter_interets_mensuels()
        assert "skipped_reason" in summary

    def test_kill_switch_reactivates_legacy_behaviour(
        self, active_member, enable_legacy_interest_cron
    ):
        """Si l'admin réactive le kill-switch, l'ancien comportement revient."""
        acc = active_member.savings_account
        acc.solde = Decimal("100000")
        acc.save(update_fields=["solde"])

        summary = crediter_interets_mensuels()
        assert summary.get("comptes_traites") == 1
        acc.refresh_from_db()
        assert acc.solde == Decimal("101000.00")
