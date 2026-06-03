"""EXT-3 — Kill-switch admin par template e-mail.

Prouve qu'un admin peut désactiver un template (`actif=False`) pour stopper
**toutes** les notifications de ce type sans déploiement, et que le skip est
tracé en audit (preuve qu'on a respecté son choix volontairement).
"""
from __future__ import annotations

import pytest

from apps_coop.audit.models import AuditLog
from apps_coop.notifications.models import EmailLog, EmailTemplate, Notification
from apps_coop.notifications.services import send_template


pytestmark = pytest.mark.django_db


def _make_template(code: str = "test.demo", actif: bool = True) -> EmailTemplate:
    return EmailTemplate.objects.create(
        code=code,
        objet="Bonjour {prenom}",
        corps_html="<p>Hello {prenom}</p>",
        corps_texte="Hello {prenom}",
        actif=actif,
    )


class TestActiveTemplateSends:
    def test_active_template_persists_emaillog(self):
        _make_template(actif=True)
        log = send_template(
            "test.demo", to="alice@example.com", context={"prenom": "Alice"}
        )
        assert log is not None
        assert isinstance(log, EmailLog)
        assert EmailLog.objects.count() == 1


class TestInactiveTemplateIsKilled:
    """Quand l'admin désactive un template, plus aucun envoi ne part."""

    def test_inactive_template_returns_none(self):
        _make_template(actif=False)
        result = send_template(
            "test.demo", to="bob@example.com", context={"prenom": "Bob"}
        )
        assert result is None

    def test_inactive_template_creates_no_emaillog(self):
        _make_template(actif=False)
        send_template("test.demo", to="bob@example.com", context={"prenom": "Bob"})
        # Aucun EmailLog n'est créé → pas de trace "envoyé/échec"
        # côté observabilité utilisateur.
        assert EmailLog.objects.count() == 0

    def test_inactive_template_records_audit_trail(self):
        """Le skip volontaire doit laisser une preuve auditée."""
        tpl = _make_template(actif=False)

        send_template(
            "test.demo", to="bob@example.com", context={"prenom": "Bob"}
        )

        audit = AuditLog.objects.filter(action="notification.skipped").first()
        assert audit is not None
        assert audit.entite_type == "EmailTemplate"
        assert audit.entite_id == tpl.id
        assert audit.details_json["code"] == "test.demo"
        assert audit.details_json["reason"] == "template_inactive"

    def test_inactive_template_creates_no_in_app_notification(self, active_member):
        _make_template(actif=False)
        send_template(
            "test.demo",
            to=active_member.user.email,
            context={"prenom": "Bob"},
            member=active_member,
        )
        assert Notification.objects.filter(user=active_member.user).count() == 0


class TestMissingTemplateStillBehaves:
    """Pas de template du tout = bug de config, pas un kill-switch admin."""

    def test_missing_template_returns_none_silently(self):
        assert (
            send_template(
                "code.qui.nexiste.pas", to="x@example.com", context={"prenom": "X"}
            )
            is None
        )

    def test_missing_template_does_not_record_skip_audit(self):
        # On ne loggue "notification.skipped" que pour un kill-switch volontaire.
        send_template("code.qui.nexiste.pas", to="x@example.com")
        assert (
            AuditLog.objects.filter(action="notification.skipped").count() == 0
        )
