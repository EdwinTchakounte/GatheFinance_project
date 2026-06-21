"""Tests LOT 11 — MicrocreditCampaign (refonte 2026 §8 / voie 3).

Couvre la fondation : modèle, validations d'ouverture/quota/montant, clôture
idempotente et le cron daily ``close_expired_campaigns``.

LOT 12 (eligibility routing) testera le flux complet
``submit_microcampaign_request`` → Member TEMPORAIRE → Loan.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.loans.microcampaign_services import (
    close_campaign,
    close_expired_campaigns,
    get_active_campaigns,
    is_campaign_open,
    validate_amount_against_campaign,
)
from apps_coop.loans.models import LoanRequest, MicrocreditCampaign
from apps_coop.members.models import Member

from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_campaign(
    *,
    nom="Test campagne",
    profil="commercants",
    date_debut=None,
    date_fin=None,
    montant_min=Decimal("5000"),
    montant_max=Decimal("50000"),
    taux=Decimal("0.10"),
    recovery_days=60,
    actif=True,
    plafond_beneficiaires=None,
    created_by=None,
) -> MicrocreditCampaign:
    today = date.today()
    return MicrocreditCampaign.objects.create(
        nom=nom,
        profil_cible=profil,
        date_debut=date_debut or today - timedelta(days=1),
        date_fin=date_fin or today + timedelta(days=30),
        montant_min=montant_min,
        montant_max=montant_max,
        taux_interet=taux,
        nb_jours_recouvrement=recovery_days,
        plafond_beneficiaires=plafond_beneficiaires,
        actif=actif,
        created_by=created_by or UserFactory(),
    )


# ---------------------------------------------------------------------------
# Modèle + Statut.TEMPORAIRE + FK microcampaign
# ---------------------------------------------------------------------------


class TestModelFoundation:
    def test_temporaire_statut_exists(self):
        assert Member.Statut.TEMPORAIRE == "temporaire"

    def test_loan_request_has_microcampaign_statuts(self):
        assert LoanRequest.Statut.EN_VALIDATION_CAMPAGNE == "en_validation_campagne"
        assert LoanRequest.Statut.REJETEE_CAMPAGNE == "rejetee_campagne"

    def test_member_can_link_to_campaign(self):
        c = _make_campaign()
        m = MemberFactory(statut=Member.Statut.TEMPORAIRE)
        m.microcampaign = c
        m.save()
        m.refresh_from_db()
        assert m.microcampaign_id == c.id
        assert c.beneficiaires.count() == 1

    def test_campaign_str_representation(self):
        c = _make_campaign(nom="Commerçants Q3")
        s = str(c)
        assert "Commerçants Q3" in s
        assert str(c.date_debut) in s


# ---------------------------------------------------------------------------
# is_campaign_open / get_active_campaigns
# ---------------------------------------------------------------------------


class TestIsCampaignOpen:
    def test_active_within_window(self):
        c = _make_campaign()
        assert is_campaign_open(c) is True

    def test_active_outside_window_past(self):
        today = date.today()
        c = _make_campaign(
            date_debut=today - timedelta(days=30),
            date_fin=today - timedelta(days=1),
        )
        assert is_campaign_open(c) is False

    def test_active_outside_window_future(self):
        today = date.today()
        c = _make_campaign(
            date_debut=today + timedelta(days=5),
            date_fin=today + timedelta(days=30),
        )
        assert is_campaign_open(c) is False

    def test_inactif_toggle(self):
        c = _make_campaign(actif=False)
        assert is_campaign_open(c) is False


class TestGetActiveCampaigns:
    def test_returns_only_open_ones(self):
        today = date.today()
        open_c = _make_campaign(nom="Open")
        _make_campaign(
            nom="Past",
            date_debut=today - timedelta(days=60),
            date_fin=today - timedelta(days=1),
        )
        _make_campaign(nom="Closed", actif=False)
        actives = list(get_active_campaigns())
        assert open_c in actives
        assert all(c.actif and c.date_debut <= today <= c.date_fin for c in actives)
        assert len(actives) == 1

    def test_filter_by_profil_cible(self):
        _make_campaign(nom="Comm", profil="commercants")
        _make_campaign(nom="Agri", profil="agriculteurs")
        qs = get_active_campaigns(profil_cible="commercants")
        assert qs.count() == 1
        assert qs.first().profil_cible == "commercants"

    def test_filter_profil_case_insensitive(self):
        _make_campaign(profil="commercants")
        assert get_active_campaigns(profil_cible="COMMERCANTS").count() == 1


# ---------------------------------------------------------------------------
# validate_amount_against_campaign
# ---------------------------------------------------------------------------


class TestValidateAmount:
    def test_in_range_ok(self):
        c = _make_campaign(montant_min=Decimal("5000"), montant_max=Decimal("50000"))
        # Pas d'exception attendue.
        validate_amount_against_campaign(c, Decimal("25000"))

    def test_below_min_raises(self):
        c = _make_campaign(montant_min=Decimal("5000"))
        with pytest.raises(ValueError, match="plancher"):
            validate_amount_against_campaign(c, Decimal("1000"))

    def test_above_max_raises(self):
        c = _make_campaign(montant_max=Decimal("50000"))
        with pytest.raises(ValueError, match="plafond"):
            validate_amount_against_campaign(c, Decimal("80000"))

    def test_zero_or_negative_raises(self):
        c = _make_campaign()
        with pytest.raises(ValueError, match="positif"):
            validate_amount_against_campaign(c, Decimal("0"))

    def test_closed_campaign_raises(self):
        c = _make_campaign(actif=False)
        with pytest.raises(ValueError, match="fermée"):
            validate_amount_against_campaign(c, Decimal("25000"))

    def test_quota_beneficiaires_raises(self):
        c = _make_campaign(plafond_beneficiaires=1)
        # Pose un bénéficiaire pour saturer le quota.
        MemberFactory(
            statut=Member.Statut.TEMPORAIRE,
            microcampaign=c,
        )
        with pytest.raises(ValueError, match="[Qq]uota"):
            validate_amount_against_campaign(c, Decimal("10000"))

    def test_quota_not_reached_ok(self):
        c = _make_campaign(plafond_beneficiaires=5)
        MemberFactory(statut=Member.Statut.TEMPORAIRE, microcampaign=c)
        # Aucun raise.
        validate_amount_against_campaign(c, Decimal("10000"))


# ---------------------------------------------------------------------------
# close_campaign
# ---------------------------------------------------------------------------


class TestCloseCampaign:
    def test_close_sets_flag_and_timestamp(self):
        c = _make_campaign()
        assert c.actif is True
        result = close_campaign(c, reason="manual")
        assert result.actif is False
        assert result.closed_at is not None
        assert result.close_reason == "manual"

    def test_idempotent_on_already_closed(self):
        c = _make_campaign()
        first = close_campaign(c)
        first_closed_at = first.closed_at
        # Deuxième passage doit être no-op (pas d'écrasement closed_at).
        second = close_campaign(c, reason="other")
        assert second.closed_at == first_closed_at
        assert second.close_reason == first.close_reason  # inchangé

    def test_close_records_audit(self):
        from apps_coop.audit.models import AuditLog

        c = _make_campaign()
        close_campaign(c, reason="manual")
        log = AuditLog.objects.filter(
            action="microcampaign.closed", entite_id=c.id
        ).first()
        assert log is not None
        assert log.details_json.get("reason") == "manual"


# ---------------------------------------------------------------------------
# close_expired_campaigns (cron)
# ---------------------------------------------------------------------------


class TestCronCloseExpired:
    def test_closes_past_date_fin(self):
        today = date.today()
        expired = _make_campaign(
            nom="Expirée",
            date_debut=today - timedelta(days=60),
            date_fin=today - timedelta(days=1),
        )
        active = _make_campaign(nom="Active")
        result = close_expired_campaigns()
        assert result["closed"] >= 1
        expired.refresh_from_db()
        active.refresh_from_db()
        assert expired.actif is False
        assert expired.close_reason == "expired"
        assert active.actif is True

    def test_no_op_when_no_expired(self):
        _make_campaign()  # encore ouverte
        result = close_expired_campaigns()
        assert result["closed"] == 0

    def test_idempotent_does_not_reclose(self):
        today = date.today()
        expired = _make_campaign(
            date_debut=today - timedelta(days=60),
            date_fin=today - timedelta(days=1),
        )
        close_expired_campaigns()
        expired.refresh_from_db()
        first_closed_at = expired.closed_at
        # Second run — must be no-op.
        result2 = close_expired_campaigns()
        assert result2["closed"] == 0
        expired.refresh_from_db()
        assert expired.closed_at == first_closed_at

    def test_task_wrapper_returns_counters(self):
        from apps_coop.loans.tasks import microcampaign_close_expired_task

        today = date.today()
        _make_campaign(
            date_debut=today - timedelta(days=60),
            date_fin=today - timedelta(days=1),
        )
        result = microcampaign_close_expired_task()
        assert "closed" in result
        assert result["closed"] >= 1


# ---------------------------------------------------------------------------
# AppSettings + cron schedule seeded
# ---------------------------------------------------------------------------


class TestAppSettingsSeed:
    def test_seed_creates_lot11_keys(self):
        from django.core.management import call_command

        call_command("seed_app_settings")
        expected = [
            "loans.campaign.default_montant_min",
            "loans.campaign.default_montant_max",
            "loans.campaign.default_taux",
            "loans.campaign.default_recovery_days",
        ]
        for key in expected:
            assert AppSetting.objects.filter(cle=key).exists(), f"missing {key}"

    def test_cron_schedule_seeded(self):
        from django.core.management import call_command
        from django_q.models import Schedule

        call_command("seed_q_schedules")
        sched = Schedule.objects.filter(name="loans.microcampaign.close_expired")
        assert sched.exists()
        assert (
            sched.first().func
            == "apps_coop.loans.tasks.microcampaign_close_expired_task"
        )
