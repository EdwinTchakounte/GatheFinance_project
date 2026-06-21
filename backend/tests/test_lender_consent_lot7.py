"""LOT 7 (refonte 2026) — Épargne-prêteur : modèles + services.

Couvre :
  - ``LenderConsent`` opt-in (mode A global ou mode B tranches)
  - ``LenderTranche`` création, garde montant min, garde consent requis
  - ``cancel_tranche`` (DISPONIBLE → ANNULEE), garde sur ENGAGEE
  - ``revoke_consent`` (idempotent, bloqué si tranche engagée)
  - Property ``Member.is_lender`` / ``Member.capacite_pretable``
    en mode A (global) et en mode B (tranches DISPONIBLE)
  - Audit log écrit sur chaque mutation
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.members.models import Member
from apps_coop.savings.lender_services import (
    add_tranche,
    cancel_tranche,
    opt_in_lender,
    revoke_consent,
)
from apps_coop.savings.models import (
    LenderConsent,
    LenderTranche,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _override_media_root(tmp_path, settings):
    """LenderConsent porte un FileField — isole MEDIA_ROOT en tmp."""
    settings.MEDIA_ROOT = str(tmp_path)


def _give_classic_savings(member: Member, *, solde: Decimal) -> ClassicSavingsAccount:
    """Pose un ClassicSavingsAccount au membre avec un solde donné."""
    acc, _ = ClassicSavingsAccount.objects.get_or_create(
        member=member,
        defaults={
            "solde": Decimal("0"),
            "date_ouverture": date.today(),
        },
    )
    acc.solde = Decimal(solde)
    acc.save(update_fields=["solde", "updated_at"])
    return acc


# ---------------------------------------------------------------------------
# Opt-in / opt-out
# ---------------------------------------------------------------------------


class TestOptInLender:
    """``opt_in_lender`` pose un consent unique par membre (idempotent)."""

    def test_first_optin_creates_consent(self, active_member):
        consent = opt_in_lender(member=active_member, is_global=True)
        assert consent.pk is not None
        assert consent.is_global is True
        assert consent.revoked_at is None
        assert consent.convention_signed_at is not None
        assert active_member.is_lender is True

    def test_optin_idempotent_when_already_active(self, active_member):
        first = opt_in_lender(member=active_member, is_global=False)
        second = opt_in_lender(member=active_member, is_global=False)
        assert first.pk == second.pk
        # Une seule ligne en DB.
        assert LenderConsent.objects.filter(member=active_member).count() == 1

    def test_optin_can_switch_mode_when_already_active(self, active_member):
        """Appel avec un is_global différent met à jour, ne re-crée pas."""
        opt_in_lender(member=active_member, is_global=False)
        updated = opt_in_lender(member=active_member, is_global=True)
        assert updated.is_global is True
        assert LenderConsent.objects.filter(member=active_member).count() == 1

    def test_optin_reactivates_revoked_consent(self, active_member):
        consent = opt_in_lender(member=active_member, is_global=True)
        consent.revoked_at = timezone.now()
        consent.save(update_fields=["revoked_at"])
        reactivated = opt_in_lender(member=active_member, is_global=False)
        assert reactivated.pk == consent.pk
        assert reactivated.revoked_at is None
        assert reactivated.is_global is False

    def test_optin_blocked_below_seniority_threshold(self, active_member):
        """Si l'admin pose un seuil d'ancienneté, l'opt-in est refusé."""
        AppSetting.objects.update_or_create(
            cle="lender.consent.min_seniority_months",
            defaults={"valeur": "12"},
        )
        # active_member a date_adhesion=today → seniority = 0 < 12
        with pytest.raises(ValueError, match="Ancienneté insuffisante"):
            opt_in_lender(member=active_member, is_global=True)

    def test_optin_writes_audit_log(self, active_member):
        opt_in_lender(member=active_member, is_global=True)
        log = AuditLog.objects.filter(action="lender.consent.opt_in").first()
        assert log is not None
        assert log.entite_type == "LenderConsent"
        assert log.details_json["member_id"] == active_member.id


# ---------------------------------------------------------------------------
# Add / cancel tranche
# ---------------------------------------------------------------------------


class TestAddTranche:
    def test_add_tranche_requires_active_consent(self, active_member):
        with pytest.raises(ValueError, match="convention prêteur"):
            add_tranche(member=active_member, montant=Decimal("10000"))

    def test_add_tranche_below_min_blocked(self, active_member):
        opt_in_lender(member=active_member, is_global=False)
        AppSetting.objects.update_or_create(
            cle="lender.tranche.min_amount",
            defaults={"valeur": "5000"},
        )
        with pytest.raises(ValueError, match="trop bas"):
            add_tranche(member=active_member, montant=Decimal("1000"))

    def test_add_tranche_ok_creates_disponible(self, active_member):
        opt_in_lender(member=active_member, is_global=False)
        tranche = add_tranche(member=active_member, montant=Decimal("50000"))
        assert tranche.statut == LenderTranche.Statut.DISPONIBLE
        assert tranche.montant == Decimal("50000")
        assert tranche.engaged_in_loan is None

    def test_add_multiple_tranches_cumulates(self, active_member):
        opt_in_lender(member=active_member, is_global=False)
        add_tranche(member=active_member, montant=Decimal("10000"))
        add_tranche(member=active_member, montant=Decimal("20000"))
        count = LenderTranche.objects.filter(
            member=active_member,
            statut=LenderTranche.Statut.DISPONIBLE,
        ).count()
        assert count == 2


class TestCancelTranche:
    def test_cancel_disponible_ok(self, active_member):
        opt_in_lender(member=active_member, is_global=False)
        tranche = add_tranche(member=active_member, montant=Decimal("10000"))
        cancelled = cancel_tranche(tranche=tranche)
        assert cancelled.statut == LenderTranche.Statut.ANNULEE

    def test_cancel_already_cancelled_idempotent(self, active_member):
        opt_in_lender(member=active_member, is_global=False)
        tranche = add_tranche(member=active_member, montant=Decimal("10000"))
        cancel_tranche(tranche=tranche)
        again = cancel_tranche(tranche=tranche)
        assert again.statut == LenderTranche.Statut.ANNULEE

    def test_cancel_engagee_blocked(self, active_member):
        """Annulation refusée si la tranche est engagée dans un crédit."""
        opt_in_lender(member=active_member, is_global=False)
        tranche = add_tranche(member=active_member, montant=Decimal("10000"))
        # Force le statut ENGAGEE (LOT 8 le fera via le funding).
        tranche.statut = LenderTranche.Statut.ENGAGEE
        tranche.save(update_fields=["statut"])
        with pytest.raises(ValueError, match="Impossible d'annuler"):
            cancel_tranche(tranche=tranche)


# ---------------------------------------------------------------------------
# Revoke consent
# ---------------------------------------------------------------------------


class TestRevokeConsent:
    def test_revoke_no_consent_raises(self, active_member):
        with pytest.raises(ValueError, match="Aucune convention"):
            revoke_consent(member=active_member)

    def test_revoke_clean_ok(self, active_member):
        opt_in_lender(member=active_member, is_global=True)
        revoked = revoke_consent(member=active_member)
        assert revoked.revoked_at is not None
        # Recharge depuis la DB : le OneToOne cache l'objet en mémoire.
        fresh = Member.objects.get(pk=active_member.pk)
        assert fresh.is_lender is False

    def test_revoke_idempotent(self, active_member):
        opt_in_lender(member=active_member, is_global=True)
        first = revoke_consent(member=active_member)
        second = revoke_consent(member=active_member)
        assert first.pk == second.pk
        assert first.revoked_at == second.revoked_at

    def test_revoke_blocked_when_tranche_engaged(self, active_member):
        opt_in_lender(member=active_member, is_global=False)
        tranche = add_tranche(member=active_member, montant=Decimal("10000"))
        tranche.statut = LenderTranche.Statut.ENGAGEE
        tranche.save(update_fields=["statut"])
        with pytest.raises(ValueError, match="tranche.*engagée"):
            revoke_consent(member=active_member)

    def test_revoke_cancels_disponible_tranches(self, active_member):
        """À la révocation, les tranches DISPONIBLE deviennent ANNULEE."""
        opt_in_lender(member=active_member, is_global=False)
        t1 = add_tranche(member=active_member, montant=Decimal("10000"))
        t2 = add_tranche(member=active_member, montant=Decimal("20000"))
        revoke_consent(member=active_member)
        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t1.statut == LenderTranche.Statut.ANNULEE
        assert t2.statut == LenderTranche.Statut.ANNULEE


# ---------------------------------------------------------------------------
# Member.capacite_pretable
# ---------------------------------------------------------------------------


class TestCapacitePretable:
    def test_zero_without_consent(self, active_member):
        assert active_member.capacite_pretable == Decimal("0.00")

    def test_zero_when_consent_revoked(self, active_member):
        opt_in_lender(member=active_member, is_global=True)
        revoke_consent(member=active_member)
        assert active_member.capacite_pretable == Decimal("0.00")

    def test_global_mode_uses_classic_savings_solde(self, active_member):
        _give_classic_savings(active_member, solde=Decimal("80000"))
        opt_in_lender(member=active_member, is_global=True)
        assert active_member.capacite_pretable == Decimal("80000")

    def test_global_mode_deducts_engaged_tranches(self, active_member):
        """En mode A, solde - tranches engagées."""
        _give_classic_savings(active_member, solde=Decimal("100000"))
        opt_in_lender(member=active_member, is_global=True)
        t = add_tranche(member=active_member, montant=Decimal("30000"))
        # Tranche DISPONIBLE → pas encore déduite (mode A regarde uniquement les engagées).
        assert active_member.capacite_pretable == Decimal("100000")
        # Engagée → déduite.
        t.statut = LenderTranche.Statut.ENGAGEE
        t.save(update_fields=["statut"])
        assert active_member.capacite_pretable == Decimal("70000")

    def test_global_mode_never_negative(self, active_member):
        _give_classic_savings(active_member, solde=Decimal("10000"))
        opt_in_lender(member=active_member, is_global=True)
        t = add_tranche(member=active_member, montant=Decimal("50000"))
        t.statut = LenderTranche.Statut.ENGAGEE
        t.save(update_fields=["statut"])
        assert active_member.capacite_pretable == Decimal("0.00")

    def test_mode_b_sums_disponible_tranches(self, active_member):
        opt_in_lender(member=active_member, is_global=False)
        add_tranche(member=active_member, montant=Decimal("10000"))
        add_tranche(member=active_member, montant=Decimal("25000"))
        assert active_member.capacite_pretable == Decimal("35000")

    def test_mode_b_ignores_engaged_and_cancelled(self, active_member):
        opt_in_lender(member=active_member, is_global=False)
        t_dispo = add_tranche(member=active_member, montant=Decimal("10000"))
        t_engaged = add_tranche(member=active_member, montant=Decimal("20000"))
        t_engaged.statut = LenderTranche.Statut.ENGAGEE
        t_engaged.save(update_fields=["statut"])
        t_cancelled = add_tranche(member=active_member, montant=Decimal("5000"))
        cancel_tranche(tranche=t_cancelled)
        # Seule la 1re tranche est DISPONIBLE.
        assert active_member.capacite_pretable == Decimal("10000")
        assert t_dispo.statut == LenderTranche.Statut.DISPONIBLE
