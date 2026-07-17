"""Support membre — fil unique membre ↔ support.

Couvre : envoi membre, lecture (marque lu), réponse staff (+ notification),
boîte admin, compteurs non-lus, gardes de permission.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps_coop.notifications.models import Notification
from apps_coop.support.models import SupportMessage, SupportThread
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


def _staff():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestMemberChannel:
    def test_post_message_cree_le_fil_et_le_message(self):
        m = MemberFactory()
        r = _api(m.user).post(
            "/api/v1/support/messages/", {"body": "Bonjour, ma collecte ?"}
        )
        assert r.status_code == 201
        assert r.data["sender"] == "member"
        assert SupportThread.objects.filter(member=m).exists()
        thread = SupportThread.objects.get(member=m)
        assert thread.last_message_at is not None
        assert thread.messages.count() == 1

    def test_message_vide_refuse(self):
        m = MemberFactory()
        r = _api(m.user).post("/api/v1/support/messages/", {"body": "   "})
        assert r.status_code == 400

    def test_get_thread_marque_les_reponses_staff_comme_lues(self):
        m = MemberFactory()
        staff = _staff()
        # membre écrit, staff répond
        _api(m.user).post("/api/v1/support/messages/", {"body": "Question"})
        thread = SupportThread.objects.get(member=m)
        _api(staff.user).post(
            f"/api/v1/support/admin/threads/{thread.id}/reply/",
            {"body": "Réponse du support"},
        )
        # avant lecture : 1 non-lu pour le membre
        assert thread.unread_for_member() == 1
        # le membre ouvre le fil → tout est marqué lu
        r = _api(m.user).get("/api/v1/support/thread/")
        assert r.status_code == 200
        assert len(r.data["messages"]) == 2
        thread.refresh_from_db()
        assert thread.unread_for_member() == 0

    def test_unread_compteur(self):
        m = MemberFactory()
        staff = _staff()
        _api(m.user).post("/api/v1/support/messages/", {"body": "Q"})
        thread = SupportThread.objects.get(member=m)
        _api(staff.user).post(
            f"/api/v1/support/admin/threads/{thread.id}/reply/", {"body": "R"}
        )
        r = _api(m.user).get("/api/v1/support/unread/")
        assert r.data["count"] == 1


class TestStaffReply:
    def test_reponse_staff_cree_message_et_notification(self):
        m = MemberFactory()
        staff = _staff()
        _api(m.user).post("/api/v1/support/messages/", {"body": "Q"})
        thread = SupportThread.objects.get(member=m)

        r = _api(staff.user).post(
            f"/api/v1/support/admin/threads/{thread.id}/reply/",
            {"body": "Nous regardons votre dossier."},
        )
        assert r.status_code == 201
        assert r.data["sender"] == "staff"
        # notification in-app créée pour le membre (déclenche aussi le push)
        notif = Notification.objects.filter(
            user=m.user, type="support.reply"
        ).first()
        assert notif is not None
        assert notif.lien == "/support"

    def test_admin_detail_marque_les_messages_membre_lus(self):
        m = MemberFactory()
        staff = _staff()
        _api(m.user).post("/api/v1/support/messages/", {"body": "Q1"})
        thread = SupportThread.objects.get(member=m)
        assert thread.unread_for_staff() == 1
        r = _api(staff.user).get(f"/api/v1/support/admin/threads/{thread.id}/")
        assert r.status_code == 200
        thread.refresh_from_db()
        assert thread.unread_for_staff() == 0

    def test_admin_threads_liste_les_fils_actifs(self):
        m = MemberFactory()
        staff = _staff()
        _api(m.user).post("/api/v1/support/messages/", {"body": "Q"})
        r = _api(staff.user).get("/api/v1/support/admin/threads/")
        assert r.status_code == 200
        assert len(r.data) >= 1
        row = r.data[0]
        assert row["member_numero"] == m.numero_membre
        assert row["staff_unread"] == 1


class TestPermissions:
    def test_anonyme_refuse(self):
        assert APIClient().get("/api/v1/support/thread/").status_code in (401, 403)

    def test_membre_non_staff_refuse_sur_admin(self):
        m = MemberFactory()
        r = _api(m.user).get("/api/v1/support/admin/threads/")
        assert r.status_code in (401, 403)
