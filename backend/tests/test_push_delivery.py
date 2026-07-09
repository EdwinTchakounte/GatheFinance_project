"""Envoi FCM HTTP v1 (`_deliver`) — succès, token invalide désactivé, no-op.

Les credentials google-auth et `requests.post` sont mockés : le test ne dépend
ni d'un vrai service account ni du réseau.
"""
from __future__ import annotations

import pytest

from apps_coop.notifications import push as pushmod
from apps_coop.notifications.models import DeviceToken

pytestmark = pytest.mark.django_db


class _Resp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def test_deliver_success(monkeypatch):
    monkeypatch.setattr(pushmod, "_fcm_credentials", lambda: ("tok", "proj"))
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["auth"] = headers.get("Authorization")
        return _Resp(200)

    monkeypatch.setattr("requests.post", fake_post)

    ok = pushmod._deliver(
        token="T1", platform="android", title="Hi", body="Body",
        data={"type": "loan.decision", "n": 7},
    )
    assert ok is True
    assert "projects/proj/messages:send" in captured["url"]
    assert captured["json"]["message"]["token"] == "T1"
    assert captured["json"]["message"]["notification"] == {"title": "Hi", "body": "Body"}
    # data : valeurs coercées en chaînes (contrainte FCM).
    assert captured["json"]["message"]["data"]["n"] == "7"
    assert captured["auth"] == "Bearer tok"


def test_deliver_unregistered_deactivates_token(monkeypatch, active_member):
    dt = DeviceToken.objects.create(
        user=active_member.user, token="DEAD", platform="android", active=True
    )
    monkeypatch.setattr(pushmod, "_fcm_credentials", lambda: ("tok", "proj"))
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: _Resp(404, '{"error":{"details":[{"errorCode":"UNREGISTERED"}]}}'),
    )
    ok = pushmod._deliver(token="DEAD", platform="android", title="H", body="B", data={})
    assert ok is False
    dt.refresh_from_db()
    assert dt.active is False


def test_deliver_noop_without_credentials(monkeypatch):
    monkeypatch.setattr(pushmod, "_fcm_credentials", lambda: None)
    assert pushmod._deliver(token="T", platform="android", title="H", body="B", data={}) is False


def test_send_push_is_noop_when_disabled(active_member, settings):
    settings.FCM_CREDENTIALS_JSON = ""
    settings.FCM_SERVER_KEY = ""
    DeviceToken.objects.create(
        user=active_member.user, token="T", platform="android", active=True
    )
    assert pushmod.send_push_to_user(active_member.user, title="H", body="B") == 0


def test_send_push_delivers_when_enabled(active_member, settings, monkeypatch):
    settings.FCM_CREDENTIALS_JSON = '{"project_id":"p"}'  # non vide → push activé
    DeviceToken.objects.create(
        user=active_member.user, token="T", platform="android", active=True
    )
    monkeypatch.setattr(pushmod, "_deliver", lambda **k: True)
    assert pushmod.send_push_to_user(active_member.user, title="H", body="B") == 1
