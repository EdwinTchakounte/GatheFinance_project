"""Middleware de sécurité — blacklist IP + auto-ban du trafic anormal.

Les tests réactivent explicitement le blocage (désactivé en dev/test par
défaut) via le fixture ``settings`` et utilisent une IP dédiée via
``REMOTE_ADDR`` pour ne jamais bannir 127.0.0.1 (le reste de la suite en dépend).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from apps_coop.audit import ip_blocklist
from apps_coop.audit.models import BlockedIP


pytestmark = pytest.mark.django_db

BAD_IP = "203.0.113.7"  # bloc de doc TEST-NET-3, jamais réel


@pytest.fixture(autouse=True)
def _reset_state():
    """Fenêtre glissante + cache propres avant/après chaque test."""
    ip_blocklist._windows.clear()
    cache.clear()
    yield
    ip_blocklist._windows.clear()
    cache.clear()


@pytest.fixture
def block_on(settings):
    settings.SECURITY_IP_BLOCK_ENABLED = True
    return settings


def _get(ip=BAD_IP, path="/api/v1/loans/campaigns/active/"):
    return Client().get(path, REMOTE_ADDR=ip)


class TestManualBlock:
    def test_active_ban_returns_403(self, block_on):
        BlockedIP.objects.create(ip=BAD_IP, reason="manual", auto=False)
        assert _get().status_code == 403

    def test_expired_ban_not_blocked(self, block_on):
        BlockedIP.objects.create(
            ip=BAD_IP,
            reason="old",
            auto=True,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        assert _get().status_code != 403

    def test_other_ip_not_blocked(self, block_on):
        BlockedIP.objects.create(ip=BAD_IP, reason="manual", auto=False)
        assert _get(ip="203.0.113.9").status_code != 403


class TestFloodAutoBan:
    def test_flood_triggers_autoban(self, block_on):
        block_on.SECURITY_IP_FLOOD_MAX_REQUESTS = 5
        block_on.SECURITY_IP_FLOOD_WINDOW_SEC = 60
        block_on.SECURITY_IP_BAN_MINUTES = 30
        # 5 requêtes passent (seuil = 5), la 6e dépasse → 403 + ban auto.
        for _ in range(5):
            assert _get().status_code != 403
        assert _get().status_code == 403
        ban = BlockedIP.objects.get(ip=BAD_IP)
        assert ban.auto is True
        assert ban.is_active()

    def test_whitelisted_ip_never_banned(self, block_on):
        block_on.SECURITY_IP_FLOOD_MAX_REQUESTS = 5
        block_on.SECURITY_IP_WHITELIST = [BAD_IP]
        for _ in range(20):
            assert _get().status_code != 403
        assert not BlockedIP.objects.filter(ip=BAD_IP).exists()


def test_disabled_lets_everything_through(settings):
    settings.SECURITY_IP_BLOCK_ENABLED = False
    BlockedIP.objects.create(ip=BAD_IP, reason="manual", auto=False)
    assert _get().status_code != 403
