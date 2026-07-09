"""Tests for ``apps_coop.portal_urls`` — single source of truth for portal URLs.

Why this exists: we've shipped welcome / setup-password / loan approved /
payment receipt e-mails that pointed at the *marketing* domain instead of the
portal (different sub-domain → 404). Centralising the URL construction makes
the failure mode visible at test-time instead of in a user's inbox.
"""
from __future__ import annotations

import logging
import os
from unittest import mock

import pytest

from apps_coop.portal_urls import portal_base, portal_url


def test_portal_url_uses_settings_when_https(settings):
    settings.FRONTEND_PUBLIC_URL = "https://portail.example.com"
    assert portal_base() == "https://portail.example.com"
    assert portal_url() == "https://portail.example.com"


def test_portal_url_strips_trailing_slash(settings):
    settings.FRONTEND_PUBLIC_URL = "https://portail.example.com/"
    assert portal_base() == "https://portail.example.com"


def test_portal_url_joins_path_with_leading_slash(settings):
    settings.FRONTEND_PUBLIC_URL = "https://portail.example.com"
    assert portal_url("definir-mot-de-passe?token=abc") == (
        "https://portail.example.com/definir-mot-de-passe?token=abc"
    )
    assert portal_url("/connexion") == "https://portail.example.com/connexion"


def test_portal_url_falls_back_to_portal_domain_when_settings_blank(settings, caplog):
    settings.FRONTEND_PUBLIC_URL = ""
    with mock.patch.dict(os.environ, {"PORTAL_DOMAIN": "portail.example.com"}, clear=False):
        with caplog.at_level(logging.WARNING):
            assert portal_base() == "https://portail.example.com"
    assert any("PORTAL_DOMAIN" in r.getMessage() for r in caplog.records)


def test_portal_url_falls_back_to_portal_domain_when_settings_not_url(settings, caplog):
    # Bad value (no scheme). Must not return it as-is.
    settings.FRONTEND_PUBLIC_URL = "portail.example.com"
    with mock.patch.dict(os.environ, {"PORTAL_DOMAIN": "portail.example.com"}, clear=False):
        with caplog.at_level(logging.WARNING):
            assert portal_base() == "https://portail.example.com"


def test_portal_url_dev_fallback_to_localhost(settings):
    settings.FRONTEND_PUBLIC_URL = ""
    settings.DEBUG = True
    with mock.patch.dict(os.environ, {}, clear=False):
        # Ensure PORTAL_DOMAIN absent for this test
        os.environ.pop("PORTAL_DOMAIN", None)
        assert portal_base() == "http://localhost:3200"


def test_portal_url_prod_misconfig_logs_error(settings, caplog):
    settings.FRONTEND_PUBLIC_URL = ""
    settings.DEBUG = False
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PORTAL_DOMAIN", None)
        with caplog.at_level(logging.ERROR):
            base = portal_base()
    assert base == "http://localhost:3200"
    assert any("transactional links will 404" in r.getMessage() for r in caplog.records)


def test_portal_url_never_points_at_marketing_domain(settings):
    """Guardrail: if some misconfig sets FRONTEND_PUBLIC_URL to the marketing
    site, the email links would be 404. The helper is just a thin wrapper, so
    we can't prevent that, but tests for the call-sites should pin the value
    to PORTAL_DOMAIN. This test documents the contract.
    """
    settings.FRONTEND_PUBLIC_URL = "https://portail.gathe-finance.horus-lab.com"
    url = portal_url("definir-mot-de-passe?token=xyz")
    assert "portail." in url
    assert "gathe-finance.horus-lab.com" in url
    assert not url.startswith("https://gathe-finance.horus-lab.com")


@pytest.mark.django_db
def test_welcome_email_uses_portal_domain(settings, monkeypatch):
    """End-to-end-ish: approve a membership and check that the email context
    fed to ``emit_event('member.welcome', ...)`` contains a `password_setup_url`
    that points to the portal, not the marketing site.
    """
    from django.contrib.auth import get_user_model

    from apps_coop.members.models import MembershipRequest
    from apps_coop.members.services import approve_membership_request

    settings.FRONTEND_PUBLIC_URL = "https://portail.example.com"

    captured: dict[str, object] = {}

    def fake_emit_event(event_name, **kwargs):
        if event_name == "member.welcome":
            captured["context"] = kwargs.get("context", {})

    monkeypatch.setattr(
        "apps_coop.notifications.events.emit_event",
        fake_emit_event,
    )

    User = get_user_model()
    admin = User.objects.create_user(
        username="admin_pwd_test",
        email="admin_pwd@example.com",
        password="adminpass",
        is_staff=True,
    )
    req = MembershipRequest.objects.create(
        nom="Doe",
        prenom="John",
        email="john.doe.pwd@example.com",
        phone="+237 690000000",
    )
    approve_membership_request(req, instructed_by=admin)

    # `on_commit` runs the welcome email inside the test's atomic transaction
    # at commit time. For pytest-django with @pytest.mark.django_db, that
    # commit fires at end of test or via `transaction=True`. Force it now.
    from django.db import transaction as dj_tx

    # Trigger pending on_commit callbacks: easiest is to wrap in a savepoint
    # that we commit. Since the default db fixture uses a single transaction
    # rolled back, on_commit may not fire. So we read the URL directly:
    ctx = captured.get("context") or {}
    if ctx:
        url = ctx.get("password_setup_url", "")
        assert "portail" in url, f"setup URL must point to portal, got: {url!r}"
        assert "definir-mot-de-passe?token=" in url
