"""Tests pour la diffusion d'annonces broadcast.

Couvre :
  - POST admin crée l'annonce + matérialise 1 Notification par membre cible
  - Audience ``actifs`` ignore les suspendus / radiés
  - Audience ``selection`` filtre par ids fournis
  - Idempotence : 2× broadcast sur la même annonce ne crée pas de doublon
  - Format mobile : message stocké en "TITRE\\n\\nCORPS" pour le parser mobile
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps_coop.members.models import Member
from apps_coop.notifications.models import Announcement, Notification
from apps_coop.notifications.services import broadcast_announcement


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def two_actifs(db, active_member, suspended_member):
    """Renvoie (actif, suspendu) prêts pour les tests d'audience."""
    return active_member, suspended_member


# ---------------------------------------------------------------------------
# Endpoint create — diffusion immédiate
# ---------------------------------------------------------------------------


def test_create_diffuse_a_tous_les_membres(admin_client, two_actifs):
    actif, suspendu = two_actifs
    res = admin_client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={
            "titre": "Fermeture exceptionnelle",
            "corps": "Vendredi 12 juin, fermeture pour formation interne.",
            "audience": "all",
        },
        format="json",
    )
    assert res.status_code == 201, res.json()
    payload = res.json()
    assert payload["titre"] == "Fermeture exceptionnelle"
    assert payload["audience"] == "all"
    # Les 2 membres ont une notif chacun.
    assert payload["recipients_count"] == 2
    assert payload["published_at"] is not None
    # Vérification base
    actif_notifs = Notification.objects.filter(user=actif.user, type="annonce")
    suspendu_notifs = Notification.objects.filter(
        user=suspendu.user, type="annonce"
    )
    assert actif_notifs.count() == 1
    assert suspendu_notifs.count() == 1


def test_audience_actifs_ignore_suspendus(admin_client, two_actifs):
    actif, suspendu = two_actifs
    res = admin_client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={
            "titre": "Seuls actifs",
            "corps": "Réservé aux membres en règle.",
            "audience": "actifs",
        },
        format="json",
    )
    assert res.status_code == 201
    assert res.json()["recipients_count"] == 1
    assert Notification.objects.filter(user=actif.user, type="annonce").exists()
    assert not Notification.objects.filter(
        user=suspendu.user, type="annonce"
    ).exists()


def test_audience_selection_filtre_par_ids(admin_client, two_actifs):
    actif, suspendu = two_actifs
    res = admin_client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={
            "titre": "Ciblée",
            "corps": "Hello.",
            "audience": "selection",
            "audience_member_ids": [actif.id],
        },
        format="json",
    )
    assert res.status_code == 201
    assert res.json()["recipients_count"] == 1
    assert Notification.objects.filter(user=actif.user, type="annonce").exists()
    assert not Notification.objects.filter(
        user=suspendu.user, type="annonce"
    ).exists()


def test_audience_selection_sans_ids_400(admin_client, two_actifs):
    res = admin_client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={
            "titre": "Vide",
            "corps": "Hello.",
            "audience": "selection",
        },
        format="json",
    )
    assert res.status_code == 400


def test_message_format_titre_double_saut_corps(admin_client, two_actifs):
    """Le mobile parse `TITRE\\n\\nCORPS` — on garantit ce format de stockage."""
    actif, _ = two_actifs
    admin_client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={
            "titre": "Avis important",
            "corps": "Détails du message.",
            "audience": "all",
        },
        format="json",
    )
    notif = Notification.objects.get(user=actif.user, type="annonce")
    assert notif.message == "Avis important\n\nDétails du message."


# ---------------------------------------------------------------------------
# Service broadcast_announcement — idempotence
# ---------------------------------------------------------------------------


def test_broadcast_idempotent(two_actifs):
    ann = Announcement.objects.create(
        titre="Maintenance",
        corps="...",
        audience=Announcement.Audience.ALL,
    )
    created1 = broadcast_announcement(ann)
    assert created1 == 2
    # Re-broadcast → 0 nouveau (les membres déjà notifiés sont skip).
    created2 = broadcast_announcement(ann)
    assert created2 == 0
    # Au total : toujours 1 notif par membre.
    assert (
        Notification.objects.filter(type="annonce").count()
        == Member.objects.count()
    )


# ---------------------------------------------------------------------------
# Endpoint list + delete
# ---------------------------------------------------------------------------


def test_list_renvoie_les_annonces(admin_client, two_actifs):
    admin_client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={"titre": "A", "corps": "a", "audience": "all"},
        format="json",
    )
    admin_client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={"titre": "B", "corps": "b", "audience": "all"},
        format="json",
    )
    res = admin_client.get("/api/v1/notifications/admin/announcements/")
    assert res.status_code == 200
    rows = res.json()["results"]
    assert len(rows) == 2
    # Ordre chronologique inverse (la plus récente d'abord).
    assert rows[0]["titre"] == "B"


def test_delete_supprime_lannonce(admin_client, two_actifs):
    res = admin_client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={"titre": "X", "corps": "x", "audience": "all"},
        format="json",
    )
    ann_id = res.json()["id"]
    del_res = admin_client.delete(
        f"/api/v1/notifications/admin/announcements/{ann_id}/"
    )
    assert del_res.status_code == 204
    assert not Announcement.objects.filter(pk=ann_id).exists()
    # Les notifications déjà reçues ne sont PAS supprimées par design.
    assert Notification.objects.filter(type="annonce").count() == 2


def test_non_staff_403(active_member):
    client = APIClient()
    client.force_authenticate(user=active_member.user)
    res = client.post(
        "/api/v1/notifications/admin/announcements/create/",
        data={"titre": "Hack", "corps": "no", "audience": "all"},
        format="json",
    )
    assert res.status_code == 403
