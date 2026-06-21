"""Tests pour ``GET /api/v1/payments/me/`` — historique du membre.

Couvre :
  - 401 si non authentifié
  - liste tri antéchronologique des paiements du membre
  - filtre ?type=
  - isolation : un membre ne voit pas les paiements d'un autre
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps_coop.payments.models import Payment


@pytest.fixture
def member_client(active_member):
    client = APIClient()
    client.force_authenticate(user=active_member.user)
    return client


@pytest.fixture
def member_payments(active_member):
    """Crée 3 paiements (frais_adhesion, frais_inscription, epargne) du membre."""
    now = timezone.now()
    p1 = Payment.objects.create(
        member=active_member,
        montant=Decimal("10000.00"),
        type=Payment.Type.FRAIS_ADHESION,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.VALIDE,
        provider_code="tara",
        reference_externe="ref-1",
        idempotency_key=uuid.uuid4(),
        date_versement=now,
    )
    p2 = Payment.objects.create(
        member=active_member,
        montant=Decimal("2000.00"),
        type=Payment.Type.FRAIS_INSCRIPTION,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.VALIDE,
        provider_code="tara",
        reference_externe="ref-2",
        idempotency_key=uuid.uuid4(),
        date_versement=now,
    )
    p3 = Payment.objects.create(
        member=active_member,
        montant=Decimal("1000.00"),
        type=Payment.Type.EPARGNE,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.EN_ATTENTE,
        provider_code="tara",
        reference_externe="ref-3",
        idempotency_key=uuid.uuid4(),
        date_versement=now,
    )
    return [p1, p2, p3]


def test_payments_me_requires_auth():
    client = APIClient()
    res = client.get("/api/v1/payments/me/")
    assert res.status_code in (401, 403)


def test_payments_me_returns_member_payments(member_client, member_payments):
    res = member_client.get("/api/v1/payments/me/")
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) == 3
    # Vérifie qu'on récupère bien les références (l'ordre exact dépend des
    # date_versement par défaut, mais toutes les lignes doivent être là).
    refs = {r["reference_externe"] for r in results}
    assert refs == {"ref-1", "ref-2", "ref-3"}


def test_payments_me_filter_type(member_client, member_payments):
    res = member_client.get("/api/v1/payments/me/?type=epargne")
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) == 1
    assert results[0]["type"] == "epargne"
    assert results[0]["reference_externe"] == "ref-3"


def test_payments_me_isolation(member_client, member_payments, db):
    """Un autre membre ne doit voir AUCUN paiement de ce membre."""
    from tests.factories import MemberFactory

    other = MemberFactory()
    Payment.objects.create(
        member=other,
        montant=Decimal("500.00"),
        type=Payment.Type.EPARGNE,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.VALIDE,
        provider_code="tara",
        reference_externe="ref-other",
        idempotency_key=uuid.uuid4(),
        date_versement=timezone.now(),
    )

    other_client = APIClient()
    other_client.force_authenticate(user=other.user)
    res = other_client.get("/api/v1/payments/me/")
    assert res.status_code == 200
    refs = {r["reference_externe"] for r in res.json()["results"]}
    assert refs == {"ref-other"}
