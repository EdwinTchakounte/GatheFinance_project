"""A2 — Réinscription annuelle (alerte douce, non bloquante).

Couvre :
  - le cron ``rappel_reinscription_annuelle`` émet ``member.reinscription_due``
    exactement J-N avant l'anniversaire (configurable via AppSetting)
  - le cron ne re-spamme pas (idempotence naturelle par fenêtre date)
  - ``confirm_member_reinscription`` décale l'ancrage de 12 mois
  - confirmation idempotente (double-clic)
  - l'événement ``member.reinscription_due`` est désactivable via EXT-5
    (couvert par les tests EXT-5 → on vérifie juste la chaîne ici)
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.members.models import Member
from apps_coop.members.services import confirm_member_reinscription
from apps_coop.members.tasks import (
    DEFAULT_LEAD_DAYS,
    rappel_reinscription_annuelle,
)
from apps_coop.notifications.models import EventConfig, EventHook, Notification


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_anchor(member: Member, *, days_ago: int) -> Member:
    """Positionne ``date_derniere_reinscription`` à today - days_ago."""
    member.date_derniere_reinscription = timezone.localdate() - timedelta(days=days_ago)
    member.save(update_fields=["date_derniere_reinscription"])
    return member


def _seed_event_catalog():
    """Seed minimal pour permettre à emit_event de fonctionner (Config + Hook EMAIL)."""
    for code, label in [
        ("member.reinscription_due", "Rappel réinscription"),
        ("member.reinscription_confirmed", "Réinscription confirmée"),
    ]:
        cfg, _ = EventConfig.objects.get_or_create(
            code=code,
            defaults={
                "label": label,
                "status": EventConfig.Status.OPTIONAL,
                "active": True,
            },
        )
        EventHook.objects.get_or_create(
            event=cfg,
            action_type=EventHook.ActionType.EMAIL,
            defaults={"target_template_code": "", "active": True},
        )


# ---------------------------------------------------------------------------
# Cron rappel J-N
# ---------------------------------------------------------------------------


class TestRappelDefaultLeadDays:
    """Avec le défaut DEFAULT_LEAD_DAYS=30."""

    def test_rappel_fires_exactly_at_anniversary_minus_30(self, active_member):
        """Un membre dont l'ancrage = today - (365 - 30) doit recevoir un rappel."""
        from django.core.management import call_command
        call_command("seed_email_templates")
        _seed_event_catalog()

        _set_anchor(active_member, days_ago=365 - DEFAULT_LEAD_DAYS)  # 335

        summary = rappel_reinscription_annuelle()

        assert summary["rappels_envoyes"] == 1
        assert summary["lead_days"] == DEFAULT_LEAD_DAYS
        # Notif in-app créée via emit_event → send_template.
        assert Notification.objects.filter(
            user=active_member.user, type="member.reinscription_due"
        ).exists()

    def test_rappel_does_not_fire_outside_window(self, active_member):
        """Ancrage = today - 100 jours → loin de l'échéance, pas de rappel."""
        from django.core.management import call_command
        call_command("seed_email_templates")
        _seed_event_catalog()

        _set_anchor(active_member, days_ago=100)
        summary = rappel_reinscription_annuelle()
        assert summary["rappels_envoyes"] == 0


class TestRappelTunableLeadDays:
    """L'admin peut changer le lead_days via AppSetting (EXT-1)."""

    def test_admin_extends_lead_to_60_days(self, active_member):
        from django.core.management import call_command
        call_command("seed_email_templates")
        _seed_event_catalog()

        AppSetting.objects.update_or_create(
            cle="members.reinscription.lead_days",
            defaults={"valeur": "60"},
        )
        _set_anchor(active_member, days_ago=365 - 60)  # 305

        summary = rappel_reinscription_annuelle()

        assert summary["lead_days"] == 60
        assert summary["rappels_envoyes"] == 1


class TestRappelRespectsKillSwitch:
    """L'admin peut couper le rappel via EventConfig.status=BLOCKED (EXT-5)."""

    def test_blocked_event_no_rappel(self, active_member):
        from django.core.management import call_command
        call_command("seed_email_templates")

        # Event seedé en BLOCKED.
        EventConfig.objects.update_or_create(
            code="member.reinscription_due",
            defaults={
                "label": "Rappel réinscription",
                "status": EventConfig.Status.BLOCKED,
                "active": False,
            },
        )

        _set_anchor(active_member, days_ago=365 - DEFAULT_LEAD_DAYS)
        summary = rappel_reinscription_annuelle()

        # Le cron a appelé emit_event qui a skippé → 0 notif.
        assert summary["rappels_envoyes"] == 1  # le cron l'a tenté
        assert not Notification.objects.filter(
            user=active_member.user, type="member.reinscription_due"
        ).exists()


# ---------------------------------------------------------------------------
# Confirmation par l'admin
# ---------------------------------------------------------------------------


class TestConfirmReinscription:
    def test_confirm_advances_anchor_to_today(self, active_member, admin_user):
        _set_anchor(active_member, days_ago=400)  # déjà en retard

        confirm_member_reinscription(active_member, confirmed_by=admin_user)

        active_member.refresh_from_db()
        assert active_member.date_derniere_reinscription == timezone.localdate()
        # Prochaine échéance = today + 365.
        assert active_member.prochaine_reinscription_due == timezone.localdate() + timedelta(days=365)

    def test_confirm_writes_audit(self, active_member, admin_user):
        _set_anchor(active_member, days_ago=400)
        confirm_member_reinscription(
            active_member,
            confirmed_by=admin_user,
            paid_amount=Decimal("12000"),
            note="Encaissement Mobile Money",
        )
        audit = AuditLog.objects.filter(
            action="member.reinscription_confirmed",
            entite_id=active_member.id,
        ).first()
        assert audit is not None
        assert audit.details_json["paid_amount"] == "12000"
        assert audit.details_json["note"] == "Encaissement Mobile Money"

    def test_confirm_is_idempotent_same_day(self, active_member, admin_user):
        """Double-clic le même jour = pas de double audit."""
        confirm_member_reinscription(active_member, confirmed_by=admin_user)
        confirm_member_reinscription(active_member, confirmed_by=admin_user)
        count = AuditLog.objects.filter(
            action="member.reinscription_confirmed",
            entite_id=active_member.id,
        ).count()
        assert count == 1


class TestAdminEndpoint:
    """A2 — POST /admin/members/<pk>/reinscription/confirm/."""

    def test_admin_can_confirm_via_api(self, client, active_member, admin_user):
        client.force_login(admin_user)
        _set_anchor(active_member, days_ago=400)

        resp = client.post(
            f"/api/v1/admin/members/{active_member.id}/reinscription/confirm/",
            data={"paid_amount": "12000", "note": "Espèces à l'agence"},
            content_type="application/json",
        )
        assert resp.status_code == 200, resp.content
        payload = resp.json()
        assert payload["date_derniere_reinscription"] == timezone.localdate().isoformat()
        assert payload["prochaine_reinscription_due"] == (
            timezone.localdate() + timedelta(days=365)
        ).isoformat()

    def test_non_admin_is_rejected(self, client, active_member):
        # Le membre lui-même ne peut pas confirmer sa propre réinscription.
        client.force_login(active_member.user)
        resp = client.post(
            f"/api/v1/admin/members/{active_member.id}/reinscription/confirm/",
            data={},
            content_type="application/json",
        )
        assert resp.status_code in (401, 403)

    def test_404_on_unknown_member(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.post(
            "/api/v1/admin/members/99999/reinscription/confirm/",
            data={},
            content_type="application/json",
        )
        assert resp.status_code == 404


class TestListFilters:
    """A2 — Filtres ``reinscription_overdue`` et ``reinscription_due_soon``
    sur GET /admin/members/."""

    def test_overdue_filter_picks_only_late_members(
        self, client, active_member, admin_user
    ):
        _set_anchor(active_member, days_ago=400)  # 400 > 365 → overdue
        client.force_login(admin_user)

        resp = client.get("/api/v1/admin/members/?reinscription_overdue=true")
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()["results"]]
        assert active_member.id in ids

    def test_overdue_filter_excludes_recent_members(
        self, client, active_member, admin_user
    ):
        _set_anchor(active_member, days_ago=100)  # tout récent
        client.force_login(admin_user)

        resp = client.get("/api/v1/admin/members/?reinscription_overdue=true")
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()["results"]]
        assert active_member.id not in ids

    def test_due_soon_filter_30_days_window(
        self, client, active_member, admin_user
    ):
        """Membre dont l'anniversaire est dans 20 jours → présent dans
        ?reinscription_due_soon=30 mais pas dans =10."""
        _set_anchor(active_member, days_ago=345)  # 365-20 = 345
        client.force_login(admin_user)

        # Fenêtre 30 jours → inclus.
        resp = client.get("/api/v1/admin/members/?reinscription_due_soon=30")
        ids = [m["id"] for m in resp.json()["results"]]
        assert active_member.id in ids

        # Fenêtre 10 jours → exclu (le membre est à J-20).
        resp = client.get("/api/v1/admin/members/?reinscription_due_soon=10")
        ids = [m["id"] for m in resp.json()["results"]]
        assert active_member.id not in ids

    def test_due_soon_filter_invalid_value_is_ignored(
        self, client, active_member, admin_user
    ):
        client.force_login(admin_user)
        resp = client.get("/api/v1/admin/members/?reinscription_due_soon=abc")
        assert resp.status_code == 200  # pas d'erreur 500
