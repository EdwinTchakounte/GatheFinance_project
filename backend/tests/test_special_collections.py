"""Tests des collectes particulières — caisse scolaire & tontine alimentaire.

Couvre le cycle complet :
  • demande de participation (et refus de doublon) ;
  • versement Mobile Money BLOQUÉ tant que la participation n'est pas validée ;
  • validation admin → versement autorisé, AVEC frais 3 % (comme tout versement
    Mobile Money) et solde crédité du montant de base ;
  • versement MANUEL (cash-in agence) → AUCUN frais ;
  • transfert interne depuis l'épargne classique disponible (et ses gardes).
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
    SpecialCollectionMembership,
    SpecialCollectionTransaction,
)

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


def _request(client, type=CAISSE, objectif="Frais scolaires de mes enfants", montant_cible=None):
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


def _membership(active_member, type=CAISSE):
    return SpecialCollectionMembership.objects.get(member=active_member, type=type)


# ── Demande de participation ──────────────────────────────────────────────────
def test_member_can_request_participation(member_client, active_member):
    res = _request(member_client, objectif="Payer la rentrée")
    assert res.status_code == 201
    body = res.json()
    assert body["statut"] == "en_attente"
    assert body["objectif"] == "Payer la rentrée"
    m = _membership(active_member)
    assert m.statut == m.Statut.EN_ATTENTE
    assert not m.is_active


def test_cannot_request_twice_while_pending(member_client):
    assert _request(member_client).status_code == 201
    assert _request(member_client).status_code == 400


# ── Versement gaté sur validation ─────────────────────────────────────────────
@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_versement_blocked_until_validated(member_client):
    _request(member_client)
    res = _momo(member_client, CAISSE, 5000)
    assert res.status_code == 403
    assert Payment.objects.filter(type=CAISSE).count() == 0


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_versement_after_validation_applies_3pct_fee(member_client, admin_client, active_member):
    _request(member_client)
    membership = _membership(active_member)
    assert _validate(admin_client, membership).status_code == 200

    res = _momo(member_client, CAISSE, 10000)
    assert res.status_code == 201
    payment = Payment.objects.get(pk=res.json()["payment"]["id"])
    # Frais 3 % en PLUS (versement Mobile Money), comme les autres versements.
    assert payment.frais_transaction == Decimal("300")

    membership.refresh_from_db()
    # Le solde est crédité du montant de BASE (le membre paie montant + frais).
    assert membership.solde == Decimal("10000")
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
    # Re-soumission autorisée après rejet.
    assert _request(member_client, objectif="Objectif clarifié").status_code == 201
    membership.refresh_from_db()
    assert membership.statut == membership.Statut.EN_ATTENTE


def test_admin_list_filters_by_type_and_statut(member_client, admin_client, active_member):
    _request(member_client, type=CAISSE)
    _request(member_client, type=TONTINE)
    res = admin_client.get("/api/v1/special-collections/admin/?type=caisse_scolaire")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["type"] == CAISSE
    assert data[0]["numero_membre"] == active_member.numero_membre


# ── Transfert interne depuis l'épargne classique ──────────────────────────────
def test_transfer_from_classic_savings(member_client, admin_client, active_member):
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("20000"), date_ouverture=_JAN
    )
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
    assert SpecialCollectionTransaction.objects.filter(
        membership=membership, type_op="transfert"
    ).count() == 1


def test_transfer_blocked_when_not_validated(member_client, active_member):
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("20000"), date_ouverture=_JAN
    )
    _request(member_client)
    res = member_client.post(
        "/api/v1/special-collections/transfer/",
        data={"type": CAISSE, "montant": 5000},
        format="json",
    )
    assert res.status_code == 400


def test_transfer_rejected_when_classic_balance_insufficient(
    member_client, admin_client, active_member
):
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("1000"), date_ouverture=_JAN
    )
    _request(member_client)
    membership = _membership(active_member)
    _validate(admin_client, membership)
    res = member_client.post(
        "/api/v1/special-collections/transfer/",
        data={"type": CAISSE, "montant": 5000},
        format="json",
    )
    assert res.status_code == 400
    membership.refresh_from_db()
    assert membership.solde == Decimal("0")
