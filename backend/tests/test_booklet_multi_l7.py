"""Tests L7 — Carnets multiples / an + imputation des écritures au plus récent.

Décisions client (2026-07-08) :
  * Chaque commande `frais_carnet` crée un nouveau BookletOrder (même en
    renouvellement annuel).
  * Les écritures d'épargne (collecte ET classique) s'imputent au carnet le
    PLUS RÉCENT du membre.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.members.models import BookletOrder
from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event
from apps_coop.savings.models import (
    ClassicSavingsTransaction,
    SavingsTransaction,
)


pytestmark = pytest.mark.django_db


def _pay(member, *, type_, montant="1000", raw=None, ref="X"):
    p = Payment.objects.create(
        member=member,
        montant=Decimal(montant),
        type=type_,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.EN_ATTENTE,
        provider_code="tara",
        date_versement=timezone.now(),
    )
    handle_webhook_event(p.idempotency_key, "valide", provider_reference=ref, raw_payload=raw or {})
    p.refresh_from_db()
    return p


def _order_carnet(member, ref):
    _pay(member, type_=Payment.Type.FRAIS_CARNET, montant="1000", ref=ref)
    return BookletOrder.latest_for(member)


class TestLatestFor:
    def test_returns_most_recent(self, active_member):
        assert BookletOrder.latest_for(active_member) is None
        o1 = _order_carnet(active_member, "C1")
        o2 = _order_carnet(active_member, "C2")
        assert o1 is not None and o2 is not None
        assert o1.id != o2.id
        assert BookletOrder.latest_for(active_member).id == o2.id


class TestMultipleCarnetsSameYear:
    def test_two_orders_same_year_create_two_booklets(self, active_member):
        _order_carnet(active_member, "C1")
        _order_carnet(active_member, "C2")
        orders = BookletOrder.objects.filter(member=active_member)
        assert orders.count() == 2
        year = timezone.localdate().year
        assert all(o.annee == year for o in orders)


class TestEcritureImputation:
    def test_collecte_deposit_attaches_to_latest_carnet(self, active_member):
        o1 = _order_carnet(active_member, "C1")
        # Dépôt collecte → rattaché au carnet le plus récent (o1).
        _pay(active_member, type_=Payment.Type.EPARGNE, montant="5000", ref="D1")
        tx1 = SavingsTransaction.objects.filter(
            account__member=active_member, type_op=SavingsTransaction.TypeOp.DEPOT
        ).latest("id")
        assert tx1.booklet_order_id == o1.id

        # Nouveau carnet → le dépôt suivant s'impute au plus récent (o2).
        o2 = _order_carnet(active_member, "C2")
        _pay(active_member, type_=Payment.Type.EPARGNE, montant="7000", ref="D2")
        tx2 = SavingsTransaction.objects.filter(
            account__member=active_member, type_op=SavingsTransaction.TypeOp.DEPOT
        ).latest("id")
        assert tx2.booklet_order_id == o2.id

    def test_classic_deposit_attaches_to_latest_carnet(self, active_member):
        o1 = _order_carnet(active_member, "C1")
        _pay(active_member, type_=Payment.Type.EPARGNE_CLASSIQUE, montant="5000", ref="DC1")
        tx = ClassicSavingsTransaction.objects.filter(
            account__member=active_member,
            type_op=ClassicSavingsTransaction.TypeOp.DEPOT,
        ).latest("id")
        assert tx.booklet_order_id == o1.id

    def test_deposit_without_carnet_is_unattached(self, active_member):
        # Aucun carnet commandé → l'écriture reste non rattachée (toléré).
        _pay(active_member, type_=Payment.Type.EPARGNE, montant="5000", ref="D0")
        tx = SavingsTransaction.objects.filter(
            account__member=active_member, type_op=SavingsTransaction.TypeOp.DEPOT
        ).latest("id")
        assert tx.booklet_order_id is None
