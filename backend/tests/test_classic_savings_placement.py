"""CH-3 — Épargne classique : sous-canal placement (vs libre).

Couvre la règle introduite dans le chantier juin 2026 : à chaque dépôt
épargne classique, le membre choisit « libre » (retrait à tout moment) ou
« placement » (mis à disposition de la convention prêteur pour financer un
crédit ; le membre touche une part des intérêts crédit via LOT 9).

Le hook est dans ``apps_coop.payments.services._hook_classic_savings_deposit``.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AppSetting
from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderConsent,
    LenderTranche,
)


pytestmark = pytest.mark.django_db


def _deposit(member, montant: str, *, is_placement: bool) -> Payment:
    """Crée et valide un dépôt épargne classique. Retourne le Payment validé."""
    payment = Payment.objects.create(
        member=member,
        montant=Decimal(montant),
        type=Payment.Type.EPARGNE_CLASSIQUE,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.EN_ATTENTE,
        provider_code="tara",
        date_versement=timezone.now(),
        is_placement=is_placement,
    )
    handle_webhook_event(
        payment.idempotency_key,
        "valide",
        provider_reference=f"TX-{payment.id}",
        raw_payload={},
    )
    payment.refresh_from_db()
    return payment


class TestDepotLibre:
    """Dépôt sans placement : alimente le solde libre, aucune tranche prêteur."""

    def test_creates_account_and_credits_balance(self, active_member):
        _deposit(active_member, "20000", is_placement=False)

        account = ClassicSavingsAccount.objects.get(member=active_member)
        assert account.solde == Decimal("20000")
        assert account.solde_libre == Decimal("20000")
        assert account.solde_placement_actif == Decimal("0")

    def test_no_lender_consent_created(self, active_member):
        _deposit(active_member, "5000", is_placement=False)
        assert not LenderConsent.objects.filter(member=active_member).exists()

    def test_no_tranche_created(self, active_member):
        _deposit(active_member, "5000", is_placement=False)
        assert not LenderTranche.objects.filter(member=active_member).exists()

    def test_transaction_flags_is_placement_false(self, active_member):
        _deposit(active_member, "5000", is_placement=False)
        tx = ClassicSavingsTransaction.objects.get(account__member=active_member)
        assert tx.is_placement is False
        assert tx.placement_unlock_date is None


class TestDepotPlacement:
    """Dépôt placement : alimente solde + crée LenderConsent + LenderTranche."""

    def test_balance_credited(self, active_member):
        _deposit(active_member, "30000", is_placement=True)
        account = ClassicSavingsAccount.objects.get(member=active_member)
        assert account.solde == Decimal("30000")

    def test_auto_creates_consent_mode_b(self, active_member):
        _deposit(active_member, "10000", is_placement=True)
        consent = LenderConsent.objects.get(member=active_member)
        assert consent.is_global is False
        assert consent.revoked_at is None
        assert consent.convention_signed_at is not None

    def test_auto_creates_disponible_tranche(self, active_member):
        _deposit(active_member, "10000", is_placement=True)
        tranche = LenderTranche.objects.get(member=active_member)
        assert tranche.montant == Decimal("10000")
        assert tranche.statut == LenderTranche.Statut.DISPONIBLE

    def test_balance_split_libre_vs_placement(self, active_member):
        _deposit(active_member, "10000", is_placement=True)
        account = ClassicSavingsAccount.objects.get(member=active_member)
        assert account.solde == Decimal("10000")
        assert account.solde_placement_actif == Decimal("10000")
        assert account.solde_libre == Decimal("0")

    def test_transaction_flag_is_placement_true(self, active_member):
        _deposit(active_member, "10000", is_placement=True)
        tx = ClassicSavingsTransaction.objects.get(account__member=active_member)
        assert tx.is_placement is True


class TestMixedDeposits:
    """Mélange libre + placement : les soldes se cumulent côté bon canal."""

    def test_two_placements_create_two_tranches_one_consent(self, active_member):
        _deposit(active_member, "5000", is_placement=True)
        _deposit(active_member, "8000", is_placement=True)

        assert LenderConsent.objects.filter(member=active_member).count() == 1
        tranches = LenderTranche.objects.filter(member=active_member).order_by("montant")
        assert tranches.count() == 2
        assert [t.montant for t in tranches] == [Decimal("5000"), Decimal("8000")]

    def test_libre_then_placement_split_correct(self, active_member):
        _deposit(active_member, "7000", is_placement=False)
        _deposit(active_member, "3000", is_placement=True)

        account = ClassicSavingsAccount.objects.get(member=active_member)
        assert account.solde == Decimal("10000")
        assert account.solde_libre == Decimal("7000")
        assert account.solde_placement_actif == Decimal("3000")

    def test_engaged_tranche_still_counts_as_placement(self, active_member):
        _deposit(active_member, "5000", is_placement=True)
        # On simule un engagement (LOT 8 funding) en passant la tranche à ENGAGEE.
        tranche = LenderTranche.objects.get(member=active_member)
        tranche.statut = LenderTranche.Statut.ENGAGEE
        tranche.engaged_at = timezone.now()
        tranche.save(update_fields=["statut", "engaged_at", "updated_at"])

        account = ClassicSavingsAccount.objects.get(member=active_member)
        # ENGAGEE compte toujours comme placement actif (donc bloqué pour le membre).
        assert account.solde_placement_actif == Decimal("5000")
        assert account.solde_libre == Decimal("0")

    def test_liberated_tranche_returns_to_libre(self, active_member):
        _deposit(active_member, "5000", is_placement=True)
        tranche = LenderTranche.objects.get(member=active_member)
        tranche.statut = LenderTranche.Statut.LIBEREE
        tranche.released_at = timezone.now()
        tranche.save(update_fields=["statut", "released_at", "updated_at"])

        account = ClassicSavingsAccount.objects.get(member=active_member)
        # LIBEREE = crédit clôturé, l'argent retourne dans le solde libre.
        assert account.solde_placement_actif == Decimal("0")
        assert account.solde_libre == Decimal("5000")


class TestKillSwitch:
    """L'AppSetting ``epargne.placement.enabled=false`` désactive le sous-canal."""

    def test_placement_disabled_no_tranche_created(self, active_member):
        AppSetting.objects.update_or_create(
            cle="epargne.placement.enabled",
            defaults={"valeur": "false"},
        )
        _deposit(active_member, "5000", is_placement=True)

        # Le solde est crédité, MAIS sans tranche prêteur — l'argent reste libre.
        account = ClassicSavingsAccount.objects.get(member=active_member)
        assert account.solde == Decimal("5000")
        assert not LenderTranche.objects.filter(member=active_member).exists()


class TestRevokedConsentReactivated:
    """Un consent révoqué est réactivé si le membre re-place."""

    def test_revoked_consent_reactivated_on_new_placement(self, active_member):
        _deposit(active_member, "5000", is_placement=True)
        consent = LenderConsent.objects.get(member=active_member)
        consent.revoked_at = timezone.now()
        consent.save(update_fields=["revoked_at", "updated_at"])

        _deposit(active_member, "3000", is_placement=True)

        consent.refresh_from_db()
        assert consent.revoked_at is None
        assert LenderTranche.objects.filter(member=active_member).count() == 2
