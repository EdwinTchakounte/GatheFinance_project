"""Tests des collectes particulières — caisse scolaire & tontine alimentaire.

Modèle par CYCLES : 1 cycle ouvert par type, re-demande à chaque cycle, clôture
= gel + archivage. Couvre : cycles (ouverture/clôture/unicité), demande gatée sur
cycle ouvert, versement (frais 3% Mobile Money, manuel = 0), transfert épargne,
et le rapprochement admin.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps_coop.payments.models import Payment
from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.special_collections.models import (
    SpecialCollectionCycle,
    SpecialCollectionMembership,
    SpecialCollectionTransaction,
)
from apps_coop.special_collections.services import open_cycle

pytestmark = pytest.mark.django_db

CAISSE = "caisse_scolaire"
TONTINE = "tontine_alimentaire"
_JAN = datetime.date(2026, 1, 1)


@pytest.fixture
def member_client(active_member):
    c = APIClient()
    c.force_authenticate(user=active_member.user)
    return c


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


def _cycle(type=CAISSE, nom="Cycle 1"):
    return open_cycle(type=type, nom=nom)


def _request(client, type=CAISSE, objectif="Frais scolaires", montant_cible=None):
    return client.post(
        "/api/v1/special-collections/request/",
        data={"type": type, "objectif": objectif, "montant_cible": montant_cible},
        format="json",
    )


def _momo(client, type, montant):
    return client.post(
        "/api/v1/payments/init/",
        data={"type": type, "montant": montant, "phone": "+237699112233", "network": "MTN"},
        format="json",
    )


def _validate(admin_client, membership):
    return admin_client.post(
        f"/api/v1/special-collections/admin/{membership.id}/validate/"
    )


def _membership(active_member, cycle=None, type=CAISSE):
    qs = SpecialCollectionMembership.objects.filter(member=active_member, type=type)
    if cycle is not None:
        qs = qs.filter(cycle=cycle)
    return qs.latest("id")


# ── Cycles ────────────────────────────────────────────────────────────────────
def test_request_fails_without_open_cycle(member_client):
    """Sans cycle ouvert, impossible de demander à participer."""
    res = _request(member_client)
    assert res.status_code == 400
    assert "cycle" in res.json()["detail"].lower()


def test_only_one_open_cycle_per_type():
    """Ouvrir un 2e cycle clôt le 1er (1 seul ouvert par type)."""
    c1 = _cycle(nom="2025")
    c2 = _cycle(nom="2026")
    c1.refresh_from_db()
    assert c1.statut == SpecialCollectionCycle.Statut.CLOS
    assert c2.statut == SpecialCollectionCycle.Statut.OUVERT
    assert (
        SpecialCollectionCycle.objects.filter(
            type=CAISSE, statut=SpecialCollectionCycle.Statut.OUVERT
        ).count()
        == 1
    )


# ── Demande de participation ──────────────────────────────────────────────────
def test_member_can_request_in_open_cycle(member_client, active_member):
    _cycle()
    res = _request(member_client, objectif="Payer la rentrée")
    assert res.status_code == 201
    assert res.json()["statut"] == "en_attente"
    m = _membership(active_member)
    assert m.statut == m.Statut.EN_ATTENTE
    assert not m.is_active


def test_cannot_request_twice_in_same_cycle(member_client):
    _cycle()
    assert _request(member_client).status_code == 201
    assert _request(member_client).status_code == 400


# ── Versement gaté ────────────────────────────────────────────────────────────
@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_versement_blocked_until_validated(member_client):
    _cycle()
    _request(member_client)
    res = _momo(member_client, CAISSE, 5000)
    assert res.status_code == 403
    assert Payment.objects.filter(type=CAISSE).count() == 0


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_versement_after_validation_applies_3pct_fee(member_client, admin_client, active_member):
    _cycle()
    _request(member_client)
    membership = _membership(active_member)
    assert _validate(admin_client, membership).status_code == 200

    res = _momo(member_client, CAISSE, 10000)
    assert res.status_code == 201
    payment = Payment.objects.get(pk=res.json()["payment"]["id"])
    assert payment.frais_transaction == Decimal("300")  # 3 %

    membership.refresh_from_db()
    assert membership.solde == Decimal("10000")  # crédité du montant de base
    assert SpecialCollectionTransaction.objects.filter(
        membership=membership, type_op="versement"
    ).count() == 1


def test_manual_cash_in_has_no_transaction_fee(admin_client, active_member):
    """Versement MANUEL (agence) → jamais de frais de transaction."""
    res = admin_client.post(
        "/api/v1/payments/admin/cash-in/",
        data={"member_id": active_member.id, "type": "epargne", "montant": 10000},
        format="json",
    )
    assert res.status_code in (200, 201)
    payment = Payment.objects.filter(
        member=active_member, source=Payment.Source.MANUEL
    ).latest("id")
    assert payment.frais_transaction == Decimal("0")


# ── Décision admin ────────────────────────────────────────────────────────────
def test_admin_reject_then_member_can_resubmit(member_client, admin_client, active_member):
    _cycle()
    _request(member_client)
    membership = _membership(active_member)
    res = admin_client.post(
        f"/api/v1/special-collections/admin/{membership.id}/reject/",
        data={"motif": "Objectif à préciser"},
        format="json",
    )
    assert res.status_code == 200
    membership.refresh_from_db()
    assert membership.statut == membership.Statut.REJETE
    assert _request(member_client, objectif="Objectif clarifié").status_code == 201
    membership.refresh_from_db()
    assert membership.statut == membership.Statut.EN_ATTENTE


def test_admin_list_filters_by_type(member_client, admin_client, active_member):
    _cycle(type=CAISSE)
    _cycle(type=TONTINE)
    _request(member_client, type=CAISSE)
    _request(member_client, type=TONTINE)
    res = admin_client.get("/api/v1/special-collections/admin/?type=caisse_scolaire")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["type"] == CAISSE
    assert data[0]["numero_membre"] == active_member.numero_membre


# ── Nouveau cycle : gel + re-demande ──────────────────────────────────────────
@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_new_cycle_freezes_old_and_requires_resubmit(
    member_client, admin_client, active_member
):
    # Cycle 1 : le membre participe et verse.
    c1 = _cycle(nom="2025")
    _request(member_client)
    m1 = _membership(active_member, cycle=c1)
    _validate(admin_client, m1)
    _momo(member_client, CAISSE, 8000)
    m1.refresh_from_db()
    assert m1.solde == Decimal("8000")

    # Cycle 2 : ouvre → c1 gelé, m1 solde figé, plus de versement possible.
    c2 = _cycle(nom="2026")
    c1.refresh_from_db()
    assert c1.statut == SpecialCollectionCycle.Statut.CLOS
    m1.refresh_from_db()
    assert m1.solde == Decimal("8000")  # gelé
    # Sans re-demande dans c2, le versement est refusé.
    assert _momo(member_client, CAISSE, 1000).status_code == 403
    # Le membre re-demande dans c2 → nouvelle participation à 0.
    assert _request(member_client).status_code == 201
    m2 = _membership(active_member, cycle=c2)
    assert m2.id != m1.id
    assert m2.solde == Decimal("0")


# ── Transfert épargne classique ───────────────────────────────────────────────
def test_transfer_from_classic_savings(member_client, admin_client, active_member):
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("20000"), date_ouverture=_JAN
    )
    _cycle()
    _request(member_client)
    membership = _membership(active_member)
    _validate(admin_client, membership)

    res = member_client.post(
        "/api/v1/special-collections/transfer/",
        data={"type": CAISSE, "montant": 5000},
        format="json",
    )
    assert res.status_code == 201
    membership.refresh_from_db()
    assert membership.solde == Decimal("5000")
    account = ClassicSavingsAccount.objects.get(member=active_member)
    assert account.solde == Decimal("15000")


def test_transfer_blocked_when_not_validated(member_client, active_member):
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("20000"), date_ouverture=_JAN
    )
    _cycle()
    _request(member_client)
    res = member_client.post(
        "/api/v1/special-collections/transfer/",
        data={"type": CAISSE, "montant": 5000},
        format="json",
    )
    assert res.status_code == 400


# ── Rapprochement admin ───────────────────────────────────────────────────────
@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_admin_cycle_reconciliation(member_client, admin_client, active_member):
    c = _cycle()
    _request(member_client)
    m = _membership(active_member)
    _validate(admin_client, m)
    _momo(member_client, CAISSE, 12000)

    res = admin_client.get(f"/api/v1/special-collections/admin/cycles/{c.id}/")
    assert res.status_code == 200
    body = res.json()
    assert body["participants_count"] == 1
    assert Decimal(body["total_collecte"]) == Decimal("12000")
    assert body["participants"][0]["numero_membre"] == active_member.numero_membre


def test_admin_open_cycle_endpoint(admin_client):
    res = admin_client.post(
        "/api/v1/special-collections/admin/cycles/",
        data={"type": CAISSE, "nom": "Caisse scolaire 2026-2027"},
        format="json",
    )
    assert res.status_code == 201
    assert res.json()["statut"] == "ouvert"
    assert res.json()["is_open"] is True
