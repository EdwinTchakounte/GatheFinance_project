"""Endpoint membre GET /api/v1/notifications/announcements/.

Vérifie l'audience (all / statut / sélection), l'exclusion des annonces
expirées, et l'exposition du corps + image (pièce jointe) au membre.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps_coop.members.models import Member
from apps_coop.notifications.models import Announcement
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _client(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def test_member_sees_all_and_status_announcements_but_not_others():
    member = MemberFactory(statut=Member.Statut.ACTIF)
    Announcement.objects.create(titre="Pour tous", corps="Bonjour à tous", audience="all")
    Announcement.objects.create(titre="Actifs", corps="Réservé actifs", audience="actifs")
    Announcement.objects.create(
        titre="Suspendus", corps="Réservé suspendus", audience="suspendus"
    )

    resp = _client(member).get(reverse("coop_notifications:my-announcements"))
    assert resp.status_code == 200
    titres = {a["titre"] for a in resp.data["results"]}
    assert "Pour tous" in titres
    assert "Actifs" in titres
    assert "Suspendus" not in titres  # audience non concernée
    # Le corps complet est bien exposé (lecture détaillée).
    all_ann = next(a for a in resp.data["results"] if a["titre"] == "Pour tous")
    assert all_ann["corps"] == "Bonjour à tous"
    assert "image_url" in all_ann


def test_expired_announcement_is_hidden():
    member = MemberFactory(statut=Member.Statut.ACTIF)
    Announcement.objects.create(
        titre="Expirée",
        corps="Ne doit pas apparaître",
        audience="all",
        expires_at=timezone.now() - timedelta(days=1),
    )
    resp = _client(member).get(reverse("coop_notifications:my-announcements"))
    assert resp.status_code == 200
    assert resp.data["results"] == []


def test_selection_audience_targets_named_member():
    target = MemberFactory(statut=Member.Statut.ACTIF)
    other = MemberFactory(statut=Member.Statut.ACTIF)
    Announcement.objects.create(
        titre="Nominative",
        corps="Pour toi uniquement",
        audience="selection",
        audience_member_ids=[target.id],
    )
    assert any(
        a["titre"] == "Nominative"
        for a in _client(target)
        .get(reverse("coop_notifications:my-announcements"))
        .data["results"]
    )
    assert not any(
        a["titre"] == "Nominative"
        for a in _client(other)
        .get(reverse("coop_notifications:my-announcements"))
        .data["results"]
    )
