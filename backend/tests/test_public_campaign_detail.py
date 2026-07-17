"""Détail public d'une campagne (deep-link partage, G8)."""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps_coop.loans.models import MicrocreditCampaign

pytestmark = pytest.mark.django_db


def _campaign(*, actif=True, closed=False):
    today = date.today()
    user = get_user_model().objects.create_user(
        username="camp-creator", password="x", is_staff=True
    )
    return MicrocreditCampaign.objects.create(
        nom="Rentrée commerçants", profil_cible="commercants",
        date_debut=today - timedelta(days=5),
        date_fin=today - timedelta(days=1) if closed else today + timedelta(days=20),
        montant_min=Decimal("50000"), montant_max=Decimal("200000"),
        taux_interet=Decimal("0.10"), nb_jours_recouvrement=90,
        plafond_beneficiaires=50, actif=actif, created_by=user,
    )


def test_detail_public_ouverte():
    c = _campaign()
    r = APIClient().get(f"/api/v1/loans/campaigns/{c.id}/")
    assert r.status_code == 200
    assert r.data["nom"] == "Rentrée commerçants"
    assert r.data["is_open"] is True
    assert r.data["flyer_url"]  # toujours une URL (stock fallback)


def test_detail_clôturée_reste_accessible():
    c = _campaign(closed=True)
    r = APIClient().get(f"/api/v1/loans/campaigns/{c.id}/")
    assert r.status_code == 200
    assert r.data["is_open"] is False


def test_detail_inexistante_404():
    assert APIClient().get("/api/v1/loans/campaigns/999999/").status_code == 404
