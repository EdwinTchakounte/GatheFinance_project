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


def test_avaliste_designe_avant_paiement_des_frais_est_visible(
    active_member, admin_user
):
    """Règle « frais d'abord, avaliste ensuite » : le mandat n'existe pas
    encore, mais la demande ne doit pas être invisible pour autant.

    Sans cette ligne synthétique, l'onglet paraissait vide alors que des
    demandes avec avaliste attendaient bel et bien.
    """
    lr = LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("250000"),
        duree_mois=6,
        motif="Avaliste désigné, frais non réglés",
        statut=LoanRequest.Statut.EN_ATTENTE,
        avaliste_numero_saisi="GF-2026-0042",
        avaliste_nom_saisi="NGONO",
    )

    client = APIClient()
    client.force_authenticate(user=admin_user)
    r = client.get("/api/v1/loans/admin/avaliste-consents/")
    assert r.status_code == 200, r.content
    body = r.json()

    assert body["counts"]["attente_frais"] == 1
    row = next(x for x in body["results"] if x["statut"] == "attente_frais")
    assert row["loan_request"]["id"] == lr.id
    assert row["avaliste"]["numero_membre"] == "GF-2026-0042"
    assert row["avaliste"]["nom"] == "NGONO"
    # Aucune caution n'est gelée tant que le mandat n'est pas émis.
    assert Decimal(row["montant_gele"]) == Decimal("0")
    # Id négatif : ne collisionne jamais avec un vrai mandat côté front.
    assert row["id"] < 0


def test_filtre_attente_frais_isole_les_demandes_non_sollicitees(
    active_member, admin_user
):
    avaliste = MemberFactory(nom="MBALLA")
    _consent(active_member, avaliste)
    LoanRequest.objects.create(
        member=MemberFactory(),
        montant_demande=Decimal("80000"),
        duree_mois=3,
        motif="Frais non réglés",
        statut=LoanRequest.Statut.EN_ATTENTE,
        avaliste_numero_saisi="GF-2026-0099",
        avaliste_nom_saisi="ATANGANA",
    )

    client = APIClient()
    client.force_authenticate(user=admin_user)

    r = client.get("/api/v1/loans/admin/avaliste-consents/?statut=attente_frais")
    assert r.status_code == 200, r.content
    rows = r.json()["results"]
    assert len(rows) == 1
    assert rows[0]["statut"] == "attente_frais"

    # Le filtre « pending » ne ramène que les vrais mandats.
    r2 = client.get("/api/v1/loans/admin/avaliste-consents/?statut=pending")
    assert all(x["statut"] == "pending" for x in r2.json()["results"])
