"""Préférences de notification push par catégorie (opt-out) + gating à l'envoi."""
from __future__ import annotations

from unittest import mock

import pytest
from rest_framework.test import APIClient

from apps_coop.notifications.preferences import (
    PUSH_CATEGORIES,
    category_for_type,
    push_allowed,
)
from apps_coop.notifications.services import create_notification

URL = "/api/v1/notifications/preferences/"


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestPreferencesApi:
    def test_defaults_all_true(self, active_member):
        res = _api(active_member.user).get(URL)
        assert res.status_code == 200
        push = res.json()["push"]
        assert set(push) == set(PUSH_CATEGORIES)
        assert all(push.values())

    def test_post_partial_merge_persists(self, active_member):
        client = _api(active_member.user)
        res = client.post(URL, {"push": {"credit": False}}, format="json")
        assert res.status_code == 200
        push = res.json()["push"]
        assert push["credit"] is False
        assert push["epargne"] is True
        # Persisté : un GET renvoie la même chose.
        again = client.get(URL).json()["push"]
        assert again["credit"] is False

    def test_post_flat_body_accepted(self, active_member):
        client = _api(active_member.user)
        res = client.post(URL, {"carnet": False}, format="json")
        assert res.status_code == 200
        assert res.json()["push"]["carnet"] is False

    def test_unknown_category_ignored(self, active_member):
        client = _api(active_member.user)
        res = client.post(URL, {"push": {"inexistant": False}}, format="json")
        assert res.status_code == 200
        assert set(res.json()["push"]) == set(PUSH_CATEGORIES)

    def test_requires_auth(self):
        assert APIClient().get(URL).status_code in (401, 403)


class TestCategoryMapping:
    def test_known_types(self):
        assert category_for_type("credit.approved") == "credit"
        assert category_for_type("epargne.depot_valide") == "epargne"
        assert category_for_type("booklet.ready") == "carnet"
        assert category_for_type("reconduction.comite") == "reconduction"
        assert category_for_type("security.password_changed") == "securite"

    def test_unmapped_is_none(self):
        assert category_for_type("annonce") is None
        assert category_for_type("support.reply") is None
        assert category_for_type("") is None
        assert category_for_type(None) is None


@pytest.mark.django_db
class TestPushGating:
    def test_push_allowed_respects_pref(self, active_member):
        user = active_member.user
        # Par défaut tout autorisé.
        assert push_allowed(user, "credit.approved") is True
        # Désactive crédit.
        _api(user).post(URL, {"push": {"credit": False}}, format="json")
        assert push_allowed(user, "credit.approved") is False
        assert push_allowed(user, "epargne.depot") is True
        # Type non catégorisé : toujours autorisé.
        assert push_allowed(user, "annonce") is True

    def test_create_notification_skips_push_when_disabled(self, active_member):
        user = active_member.user
        _api(user).post(URL, {"push": {"credit": False}}, format="json")
        with mock.patch(
            "apps_coop.notifications.push.send_push_to_user"
        ) as send:
            create_notification(user=user, type="credit.approved", message="x")
            send.assert_not_called()
            create_notification(user=user, type="epargne.depot", message="y")
            send.assert_called_once()
