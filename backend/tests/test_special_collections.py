"""Tests des collectes particulières — caisse scolaire & tontine alimentaire.

Modèle par COLLECTES (2026-08) : PLUSIEURS collectes ouvertes par type, chacune
avec titre + plancher par versement + description ; verser exige d'avoir acheté
le carnet du type (tontine/caisse) ; participation par collecte ; clôture admin
individuelle (gel + archivage). Couvre : multi-cycles, demande/versement ciblés,
carnet requis, plancher, frais 3% Mobile Money / 0 manuel, transfert, rapprochement.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps_coop.members.models import BookletOrder
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

_CARNET_TYPE = {
    CAISSE: BookletOrder.Type.CAISSE_SCOLAIRE,
    TONTINE: BookletOrder.Type.TONTINE,
}
_CARNET_PAYMENT_TYPE = {
    CAISSE: Payment.Type.FRAIS_CARNET_CAISSE,
    TONTINE: Payment.Type.FRAIS_CARNET_TONTINE,
}


def _give_carnet(member, collection_type=CAISSE):
    """Dote le membre du carnet requis pour verser dans ce type de collecte."""
    p = Payment.objects.create(
        member=member,
        montant=Decimal("1000"),
        type=_CARNET_PAYMENT_TYPE[collection_type],
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
    )
    return BookletOrder.objects.create(
        member=member, type=_CARNET_TYPE[collection_type], payment=p
    )


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


# ── Régression : chemins /payments/init réels (whitelist des types) ──────────
@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_buy_tontine_carnet_via_init(member_client, active_member):
    """L'achat du carnet tontine passe par /payments/init sans montant (tarif
    autoritaire). Régression : le type doit être accepté par la whitelist."""
    from apps_coop.members.models import BookletOrder
    from apps_coop.payments.models import FeeType

    FeeType.objects.update_or_create(
        code=FeeType.Code.CARNET_TONTINE,
        defaults={"libelle": "Carnet tontine", "montant": 1000, "actif": True},
    )
    r = member_client.post(
        "/api/v1/payments/init/",
        data={"type": "frais_carnet_tontine", "phone": "+237699112233",
              "network": "MTN"},
        format="json",
    )
    assert r.status_code == 201, r.content
    # Auto-validé → le carnet TONTINE est créé.
    assert BookletOrder.objects.filter(
        member=active_member, type=BookletOrder.Type.TONTINE
    ).exists()


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_group_cotisation_via_init_accepted(member_client, active_member):
    """Cotisation tontine de groupe via /payments/init (type accepté + gating
    roster). Régression : type tontine_groupe dans la whitelist."""
    from apps_coop.special_collections.group_services import create_group
    from apps_coop.special_collections.models import GroupTontine

    group = create_group(
        nom="Réunion test",
        roster=[{"member": active_member, "role": "membre"}],
    )
    r = member_client.post(
        "/api/v1/payments/init/",
        data={"type": "tontine_groupe", "group_id": group.id, "montant": 5000,
              "phone": "+237699112233", "network": "MTN"},
        format="json",
    )
    assert r.status_code == 201, r.content
    group = GroupTontine.objects.get(pk=group.id)
    assert group.solde == Decimal("5000")  # cagnotte créditée après validation


def test_credit_versement_fallback_legacy_payment(admin_client, active_member):
    """Rétro-compat : un paiement caisse/tontine SANS special_cycle (legacy,
    initié avant le champ) est imputé au cycle ouvert courant au lieu de bloquer."""
    from apps_coop.payments.models import Payment
    from apps_coop.special_collections.models import SpecialCollectionMembership
    from apps_coop.special_collections.services import credit_versement, open_cycle

    cycle = open_cycle(type=CAISSE, nom="Legacy")
    membership = SpecialCollectionMembership.objects.create(
        member=active_member, cycle=cycle, type=CAISSE,
        statut=SpecialCollectionMembership.Statut.VALIDE, objectif="x",
    )
    p = Payment.objects.create(
        member=active_member, montant=Decimal("3000"), type=CAISSE,
        source=Payment.Source.MANUEL, statut=Payment.Statut.VALIDE,
        date_versement=timezone.now(), date_validation=timezone.now(),
        special_cycle=None,  # legacy : pas de cycle cible
    )
    credit_versement(p)
    membership.refresh_from_db()
    assert membership.solde == Decimal("3000")


# ── Cycles ────────────────────────────────────────────────────────────────────
def test_request_fails_without_open_cycle(member_client):
    """Sans collecte ouverte, impossible de demander à participer."""
    res = _request(member_client)
    assert res.status_code == 400
    assert "collecte" in res.json()["detail"].lower()


def test_multiple_open_cycles_per_type():
    """2026-08 : plusieurs collectes du même type peuvent être ouvertes en
    parallèle (ouvrir la 2e ne clôt PLUS la 1re)."""
    c1 = _cycle(nom="Tontine A")
    c2 = _cycle(nom="Tontine B")
    c1.refresh_from_db()
    assert c1.statut == SpecialCollectionCycle.Statut.OUVERT
    assert c2.statut == SpecialCollectionCycle.Statut.OUVERT
    assert (
        SpecialCollectionCycle.objects.filter(
            type=CAISSE, statut=SpecialCollectionCycle.Statut.OUVERT
        ).count()
        == 2
    )


def test_member_participates_in_two_cycles_same_type(member_client, active_member):
    """Un membre peut demander à participer à DEUX collectes du même type."""
    c1 = _cycle(nom="Tontine A")
    c2 = _cycle(nom="Tontine B")
    r1 = member_client.post(
        "/api/v1/special-collections/request/",
        data={"type": CAISSE, "cycle_id": c1.id, "objectif": "A"},
        format="json",
    )
    r2 = member_client.post(
        "/api/v1/special-collections/request/",
        data={"type": CAISSE, "cycle_id": c2.id, "objectif": "B"},
        format="json",
    )
    assert r1.status_code == 201 and r2.status_code == 201
    assert SpecialCollectionMembership.objects.filter(
        member=active_member, type=CAISSE
    ).count() == 2


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
    _give_carnet(active_member, CAISSE)
    _request(member_client)
    membership = _membership(active_member)
    assert _validate(admin_client, membership).status_code == 200

    res = _momo(member_client, CAISSE, 10000)
    assert res.status_code == 201, res.content
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


# ── Clôture admin individuelle (gel) ─────────────────────────────────────────
@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_admin_close_freezes_only_that_cycle(
    member_client, admin_client, active_member
):
    """La clôture admin gèle UNE collecte précise ; ouvrir une 2e ne gèle rien."""
    c1 = _cycle(nom="Tontine A")
    _give_carnet(active_member, CAISSE)
    member_client.post(
        "/api/v1/special-collections/request/",
        data={"type": CAISSE, "cycle_id": c1.id, "objectif": "A"},
        format="json",
    )
    m1 = _membership(active_member, cycle=c1)
    _validate(admin_client, m1)
    _momo(member_client, CAISSE, 8000)  # une seule ouverte → cycle déduit
    m1.refresh_from_db()
    assert m1.solde == Decimal("8000")

    # Ouvrir une 2e collecte ne gèle PAS la 1re.
    _cycle(nom="Tontine B")
    c1.refresh_from_db()
    assert c1.statut == SpecialCollectionCycle.Statut.OUVERT

    # L'admin clôture explicitement c1 → gelée, plus de versement dessus.
    assert admin_client.post(
        f"/api/v1/special-collections/admin/cycles/{c1.id}/close/"
    ).status_code == 200
    c1.refresh_from_db()
    assert c1.statut == SpecialCollectionCycle.Statut.CLOS
    m1.refresh_from_db()
    assert m1.solde == Decimal("8000")  # solde figé
    # Un versement ciblant explicitement la collecte close est refusé.
    res = member_client.post(
        "/api/v1/payments/init/",
        data={
            "type": CAISSE, "cycle_id": c1.id, "montant": 1000,
            "phone": "+237699112233", "network": "MTN",
        },
        format="json",
    )
    assert res.status_code == 400


# ── Transfert épargne classique ───────────────────────────────────────────────
def test_transfer_from_classic_savings(member_client, admin_client, active_member):
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("20000"), date_ouverture=_JAN
    )
    _cycle()
    _give_carnet(active_member, CAISSE)
    _request(member_client)
    membership = _membership(active_member)
    _validate(admin_client, membership)

    res = member_client.post(
        "/api/v1/special-collections/transfer/",
        data={"type": CAISSE, "montant": 5000},
        format="json",
    )
    assert res.status_code == 201, res.content
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
    _give_carnet(active_member, CAISSE)
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


def test_cash_in_caisse_scolaire_credits_membership(admin_client, member_client, active_member):
    """Cash-in manuel caisse scolaire → crédite la participation validée du membre."""
    _cycle()
    _give_carnet(active_member, CAISSE)
    _request(member_client)
    m = _membership(active_member)
    _validate(admin_client, m)
    res = admin_client.post(
        "/api/v1/payments/admin/cash-in/",
        data={"member_id": active_member.id, "type": "caisse_scolaire", "montant": 5000},
        format="json",
    )
    assert res.status_code in (200, 201), res.content
    m.refresh_from_db()
    assert m.solde == Decimal("5000")  # crédité, sans frais (manuel)
    # Provenance « manuel » (agence), pas Mobile Money.
    row = SpecialCollectionTransaction.objects.filter(membership=m).latest("id")
    assert row.type_op == SpecialCollectionTransaction.TypeOp.MANUEL


def test_cash_in_sells_typed_carnet(admin_client, active_member):
    """Régression : l'admin peut vendre en agence le carnet tontine/caisse
    (parité MoMo). Crée un BookletOrder du bon type."""
    from apps_coop.members.models import BookletOrder
    from apps_coop.payments.models import FeeType

    FeeType.objects.update_or_create(
        code=FeeType.Code.CARNET_CAISSE,
        defaults={"libelle": "Carnet caisse", "montant": 1000, "actif": True},
    )
    res = admin_client.post(
        "/api/v1/payments/admin/cash-in/",
        data={"member_id": active_member.id, "type": "frais_carnet_caisse",
              "montant": 1000},
        format="json",
    )
    assert res.status_code in (200, 201), res.content
    assert BookletOrder.objects.filter(
        member=active_member, type=BookletOrder.Type.CAISSE_SCOLAIRE
    ).exists()


# ── Carnet requis + plancher par versement (règles 2026-08) ──────────────────
@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_versement_refuse_sans_carnet(member_client, admin_client, active_member):
    """Sans carnet du type, le versement est refusé (achat carnet requis)."""
    _cycle()
    _request(member_client)
    _validate(admin_client, _membership(active_member))
    res = _momo(member_client, CAISSE, 5000)
    assert res.status_code == 400
    assert "carnet" in res.json()["detail"].lower()


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_versement_refuse_sous_le_plancher(member_client, admin_client, active_member):
    """Un versement sous le montant minimal de la collecte est refusé."""
    open_cycle(type=CAISSE, nom="Plancher 2000", montant_minimal=Decimal("2000"))
    _give_carnet(active_member, CAISSE)
    _request(member_client)
    _validate(admin_client, _membership(active_member))
    # 1500 < plancher 2000 → refus
    assert _momo(member_client, CAISSE, 1500).status_code == 400
    # 2500 ≥ plancher → OK
    assert _momo(member_client, CAISSE, 2500).status_code == 201


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_invalidate_reverses_special_collection_deposit(
    member_client, admin_client, active_member, admin_user
):
    """Rollback : invalider un versement caisse/tontine débite la participation."""
    from apps_coop.payments.invalidation_services import invalidate_payment
    from apps_coop.payments.models import Payment

    _cycle()
    _give_carnet(active_member, CAISSE)
    _request(member_client)
    m = _membership(active_member)
    _validate(admin_client, m)
    _momo(member_client, CAISSE, 10000)
    m.refresh_from_db()
    assert m.solde == Decimal("10000")
    pay = Payment.objects.filter(
        member=active_member, type=CAISSE, statut=Payment.Statut.VALIDE
    ).latest("id")
    invalidate_payment(pay, actor=admin_user)
    m.refresh_from_db()
    assert m.solde == Decimal("0")  # participation ramenée
