"""Lot D — bases notifications push : DeviceToken + endpoints + no-op push."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps_coop.notifications.models import DeviceToken, Notification
from apps_coop.notifications.push import push_enabled, send_push_to_user
from apps_coop.notifications.services import create_notification
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestDeviceRegistration:
    def test_register_creates_token(self):
        m = MemberFactory()
        res = _client(m.user).post(
            "/api/v1/notifications/devices/register/",
            {"token": "abc123", "platform": "android"},
            format="json",
        )
        assert res.status_code == 200
        dt = DeviceToken.objects.get(token="abc123")
        assert dt.user_id == m.user.id
        assert dt.platform == "android"
        assert dt.active is True

    def test_register_is_idempotent(self):
        m = MemberFactory()
        c = _client(m.user)
        c.post("/api/v1/notifications/devices/register/", {"token": "t"}, format="json")
        c.post("/api/v1/notifications/devices/register/", {"token": "t"}, format="json")
        assert DeviceToken.objects.filter(token="t").count() == 1

    def test_register_requires_token(self):
        m = MemberFactory()
        res = _client(m.user).post(
            "/api/v1/notifications/devices/register/", {}, format="json"
        )
        assert res.status_code == 400

    def test_unregister_deactivates(self):
        m = MemberFactory()
        c = _client(m.user)
        c.post("/api/v1/notifications/devices/register/", {"token": "z"}, format="json")
        res = c.post(
            "/api/v1/notifications/devices/unregister/", {"token": "z"}, format="json"
        )
        assert res.status_code == 200
        assert DeviceToken.objects.get(token="z").active is False


class TestPushService:
    def test_push_disabled_by_default(self):
        assert push_enabled() is False

    def test_send_push_is_noop_without_provider(self):
        m = MemberFactory()
        DeviceToken.objects.create(user=m.user, token="k", platform="android")
        # Aucun fournisseur configuré → 0 envoi, pas d'exception.
        assert send_push_to_user(m.user, title="T", body="B") == 0

    def test_create_notification_still_works_with_devices(self):
        m = MemberFactory()
        DeviceToken.objects.create(user=m.user, token="k2", platform="android")
        n = create_notification(user=m.user, type="test.x", message="Coucou")
        assert Notification.objects.filter(pk=n.pk).exists()
        assert n.message == "Coucou"
