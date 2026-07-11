"""Lot C — commentaires en fil de discussion (1 niveau) + notif de l'auteur.

Cible = une MicrocreditCampaign (kind="campaign").
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import MicrocreditCampaign
from apps_coop.notifications.models import Notification
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def campaign(admin_user):
    today = date.today()
    return MicrocreditCampaign.objects.create(
        nom="Test", profil_cible="commercants",
        date_debut=today - timedelta(days=5),
        date_fin=today + timedelta(days=30),
        montant_min=Decimal("5000"), montant_max=Decimal("50000"),
        taux_interet=Decimal("0.10"), nb_jours_recouvrement=60,
        actif=True, created_by=admin_user,
    )


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _url(campaign):
    return f"/api/v1/social/campaigns/{campaign.id}/comments/"


class TestThreads:
    def test_root_comment_has_empty_replies(self, campaign):
        a = MemberFactory()
        c = _client(a.user)
        r = c.post(_url(campaign), {"body": "Bonjour"}, format="json")
        assert r.status_code == 201, r.data
        assert r.data["parent_id"] is None
        assert r.data["replies"] == []
        assert r.data["reply_count"] == 0

    def test_reply_is_nested_under_root(self, campaign):
        a, b = MemberFactory(), MemberFactory()
        root = _client(a.user).post(_url(campaign), {"body": "Question ?"}, format="json").data
        rep = _client(b.user).post(
            _url(campaign), {"body": "Reponse !", "parent_id": root["id"]}, format="json"
        )
        assert rep.status_code == 201, rep.data
        assert rep.data["parent_id"] == root["id"]

        listing = _client(a.user).get(_url(campaign)).data
        # Un seul commentaire racine paginé, avec sa réponse imbriquée.
        assert listing["count"] == 1
        assert len(listing["results"]) == 1
        node = listing["results"][0]
        assert node["reply_count"] == 1
        assert node["replies"][0]["body"] == "Reponse !"

    def test_reply_to_reply_collapses_to_root(self, campaign):
        a, b = MemberFactory(), MemberFactory()
        root = _client(a.user).post(_url(campaign), {"body": "R"}, format="json").data
        rep = _client(b.user).post(
            _url(campaign), {"body": "r1", "parent_id": root["id"]}, format="json"
        ).data
        # On répond à la réponse → doit se rattacher à la racine.
        rep2 = _client(a.user).post(
            _url(campaign), {"body": "r2", "parent_id": rep["id"]}, format="json"
        ).data
        assert rep2["parent_id"] == root["id"]

        listing = _client(a.user).get(_url(campaign)).data
        assert listing["count"] == 1
        assert listing["results"][0]["reply_count"] == 2

    def test_reply_notifies_parent_author(self, campaign):
        a, b = MemberFactory(), MemberFactory()
        root = _client(a.user).post(_url(campaign), {"body": "Hello"}, format="json").data
        _client(b.user).post(
            _url(campaign), {"body": "Salut", "parent_id": root["id"]}, format="json"
        )
        notifs = Notification.objects.filter(user=a.user, type="comment.reply")
        assert notifs.count() == 1
        assert "repondu" in notifs.first().message.lower()

    def test_reply_to_self_does_not_notify(self, campaign):
        a = MemberFactory()
        root = _client(a.user).post(_url(campaign), {"body": "Hello"}, format="json").data
        _client(a.user).post(
            _url(campaign), {"body": "suite", "parent_id": root["id"]}, format="json"
        )
        assert Notification.objects.filter(user=a.user, type="comment.reply").count() == 0

    def test_bad_parent_rejected(self, campaign):
        a = MemberFactory()
        r = _client(a.user).post(
            _url(campaign), {"body": "x", "parent_id": 999999}, format="json"
        )
        assert r.status_code == 400


class TestAdminReply:
    """Réponse officielle du staff depuis le dashboard admin."""

    def _admin_reply_url(self, pk):
        return f"/api/v1/social/admin/comments/{pk}/reply/"

    def test_admin_reply_is_staff_authored_and_notifies(self, campaign, admin_user):
        member = MemberFactory()
        root = _client(member.user).post(
            _url(campaign), {"body": "Ma question"}, format="json"
        ).data
        n_before = Notification.objects.filter(user=member.user).count()

        r = _client(admin_user).post(
            self._admin_reply_url(root["id"]),
            {"body": "Réponse officielle de l'équipe."},
            format="json",
        )
        assert r.status_code == 201, r.data
        assert r.data["parent_id"] == root["id"]
        assert r.data["is_staff_author"] is True
        assert r.data["body"] == "Réponse officielle de l'équipe."
        # L'auteur du commentaire est notifié.
        assert Notification.objects.filter(user=member.user).count() == n_before + 1

    def test_member_reply_is_not_staff_authored(self, campaign):
        a = MemberFactory()
        root = _client(a.user).post(_url(campaign), {"body": "Q"}, format="json").data
        assert root["is_staff_author"] is False

    def test_non_staff_cannot_use_admin_reply(self, campaign):
        member = MemberFactory()
        root = _client(member.user).post(_url(campaign), {"body": "Q"}, format="json").data
        r = _client(member.user).post(
            self._admin_reply_url(root["id"]), {"body": "x"}, format="json"
        )
        assert r.status_code in (403, 401)
