"""Onglet admin « Avalistes / cautions » — liste de supervision des mandats.

GET /loans/admin/avaliste-consents/ (IsStaff) : tous les AvalisteConsent avec
demandeur + garant + caution gelée + statut, filtrables par statut et recherche.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import AvalisteConsent, LoanRequest

from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


def _consent(borrower, avaliste, *, statut=AvalisteConsent.Statut.PENDING):
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test avaliste admin",
        statut=LoanRequest.Statut.EN_ATTENTE_AVALISTE,
    )
    return AvalisteConsent.objects.create(
        loan_request=lr,
        avaliste=avaliste,
        statut=statut,
        epargne_borrower_at_request=Decimal("0"),
        epargne_avaliste_at_request=Decimal("100000"),
        couverture_ratio=Decimal("1.0"),
        montant_caution=Decimal("100000"),
        identification_numero_saisi=avaliste.numero_membre,
        identification_nom_saisi=avaliste.nom,
    )


def test_admin_lists_all_consents_with_both_parties(active_member, admin_user):
    avaliste = MemberFactory(nom="DUPONT")
    _consent(active_member, avaliste)

    client = APIClient()
    client.force_authenticate(user=admin_user)
    r = client.get("/api/v1/loans/admin/avaliste-consents/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["count"] == 1
    row = body["results"][0]
    # Les deux parties sont exposées + la caution gelée.
    assert row["demandeur"]["id"] == active_member.id
    assert row["avaliste"]["nom"] == "DUPONT"
    assert Decimal(row["montant_gele"]) == Decimal("100000")
    assert body["counts"]["pending"] == 1


def test_admin_filter_by_statut(active_member, admin_user):
    av1 = MemberFactory(nom="A")
    av2 = MemberFactory(nom="B")
    _consent(active_member, av1, statut=AvalisteConsent.Statut.PENDING)
    _consent(active_member, av2, statut=AvalisteConsent.Statut.ACCEPTED)

    client = APIClient()
    client.force_authenticate(user=admin_user)
    r = client.get("/api/v1/loans/admin/avaliste-consents/?statut=accepted")
    assert r.status_code == 200
    rows = r.json()["results"]
    assert len(rows) == 1
    assert rows[0]["statut"] == "accepted"


def test_non_staff_forbidden(active_member):
    client = APIClient()
    client.force_authenticate(user=active_member.user)
    r = client.get("/api/v1/loans/admin/avaliste-consents/")
    assert r.status_code in (401, 403)
