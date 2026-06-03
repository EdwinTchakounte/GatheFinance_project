"""EXT-5 — Moteur d'événements ``emit_event`` (définition ↔ exécution dissociées).

Prouve que :
  - un événement REQUIRED tire toujours, même si ``active=False``
  - un événement OPTIONAL respecte le toggle ``active``
  - un événement BLOCKED ne tire jamais (kill-switch)
  - les hooks EMAIL multiples (ordering) sont tous exécutés
  - chaque émission, skip, et hook exécuté est tracé en audit
  - le fallback rétrocompat (pas d'EventConfig) appelle quand même ``send_template``
"""
from __future__ import annotations

import pytest

from apps_coop.audit.models import AuditLog
from apps_coop.notifications.events import emit_event
from apps_coop.notifications.models import (
    EmailLog,
    EmailTemplate,
    EventConfig,
    EventHook,
)


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_template(code: str = "test.demo") -> EmailTemplate:
    return EmailTemplate.objects.create(
        code=code,
        objet="Hello {prenom}",
        corps_html="<p>{prenom}</p>",
        corps_texte="{prenom}",
        actif=True,
    )


def _make_event(
    code: str = "test.demo",
    status: str = EventConfig.Status.OPTIONAL,
    active: bool = True,
    with_hook: bool = True,
) -> EventConfig:
    cfg = EventConfig.objects.create(
        code=code, label=code, status=status, active=active, sensitive=False
    )
    if with_hook:
        EventHook.objects.create(
            event=cfg,
            action_type=EventHook.ActionType.EMAIL,
            target_template_code="",  # fallback sur event.code
            active=True,
        )
    return cfg


# ---------------------------------------------------------------------------
# Comportement par statut
# ---------------------------------------------------------------------------


class TestStatusGate:
    def test_optional_active_fires(self, active_member):
        _make_template()
        _make_event(status=EventConfig.Status.OPTIONAL, active=True)
        result = emit_event(
            "test.demo", member=active_member, context={"prenom": "Alice"}
        )
        assert result["fired"] is True
        assert result["hooks_run"] == 1
        assert EmailLog.objects.count() == 1

    def test_optional_inactive_is_skipped(self, active_member):
        _make_template()
        _make_event(status=EventConfig.Status.OPTIONAL, active=False)
        result = emit_event(
            "test.demo", member=active_member, context={"prenom": "Alice"}
        )
        assert result["fired"] is False
        assert result["reason"] == "optional_inactive"
        assert EmailLog.objects.count() == 0

    def test_required_fires_even_if_active_false(self, active_member):
        # status=REQUIRED → l'admin ne peut pas couper, peu importe ``active``.
        _make_template()
        _make_event(status=EventConfig.Status.REQUIRED, active=False)
        result = emit_event(
            "test.demo", member=active_member, context={"prenom": "Alice"}
        )
        assert result["fired"] is True
        assert EmailLog.objects.count() == 1

    def test_blocked_never_fires(self, active_member):
        _make_template()
        _make_event(status=EventConfig.Status.BLOCKED, active=True)
        result = emit_event(
            "test.demo", member=active_member, context={"prenom": "Alice"}
        )
        assert result["fired"] is False
        assert result["reason"] == "blocked"
        assert EmailLog.objects.count() == 0


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


class TestHookExecution:
    def test_inactive_hook_not_run(self, active_member):
        _make_template()
        cfg = _make_event(with_hook=False)
        EventHook.objects.create(
            event=cfg,
            action_type=EventHook.ActionType.EMAIL,
            active=False,
        )
        result = emit_event(
            "test.demo", member=active_member, context={"prenom": "Alice"}
        )
        assert result["fired"] is True  # cfg actif…
        assert result["hooks_run"] == 0  # …mais aucun hook actif
        assert EmailLog.objects.count() == 0

    def test_multiple_hooks_all_executed(self, active_member):
        # Deux templates différents branchés sur le même événement,
        # ordering croissant.
        _make_template("test.demo")
        EmailTemplate.objects.create(
            code="test.demo.admin",
            objet="Notif admin",
            corps_html="<p>{prenom}</p>",
            corps_texte="{prenom}",
            actif=True,
        )
        cfg = _make_event(with_hook=False)
        EventHook.objects.create(
            event=cfg,
            action_type=EventHook.ActionType.EMAIL,
            target_template_code="test.demo",
            ordering=1,
        )
        EventHook.objects.create(
            event=cfg,
            action_type=EventHook.ActionType.EMAIL,
            target_template_code="test.demo.admin",
            ordering=2,
        )
        result = emit_event(
            "test.demo", member=active_member, context={"prenom": "Alice"}
        )
        assert result["hooks_run"] == 2
        # 2 EmailLog créés, 1 par template.
        codes = set(EmailLog.objects.values_list("template_id", flat=True))
        assert codes == {"test.demo", "test.demo.admin"}


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class TestAuditTrail:
    def test_emission_writes_audit(self, active_member):
        _make_template()
        _make_event()
        emit_event("test.demo", member=active_member, context={"prenom": "Alice"})
        audit = AuditLog.objects.filter(action="event.test.demo").first()
        assert audit is not None
        assert audit.details_json["hooks_run"] == 1

    def test_skip_writes_audit_with_reason(self, active_member):
        _make_template()
        _make_event(status=EventConfig.Status.BLOCKED)
        emit_event("test.demo", member=active_member)
        audit = AuditLog.objects.filter(action="event.skipped").first()
        assert audit is not None
        assert audit.details_json["reason"] == "blocked"
        assert audit.details_json["code"] == "test.demo"


# ---------------------------------------------------------------------------
# Fallback rétrocompat
# ---------------------------------------------------------------------------


class TestFallbackWhenConfigMissing:
    """Si EventConfig n'est pas seedé, on retombe sur send_template direct
    (le système continue à fonctionner pendant le déploiement)."""

    def test_no_config_falls_back_to_send_template(self, active_member):
        # Template existe, mais aucun EventConfig en base.
        _make_template("orphan.event")
        assert EventConfig.objects.filter(code="orphan.event").count() == 0

        result = emit_event(
            "orphan.event", member=active_member, context={"prenom": "Alice"}
        )

        assert result["reason"] == "fallback_no_config"
        assert result["fired"] is True
        assert EmailLog.objects.count() == 1
