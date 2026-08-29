"""État global des paiements — endpoint ``GET /payments/admin/stats/``.

Totaux essentiels (validés / en attente / rejetés) + ventilation par type,
agrégés sur TOUS les paiements et filtrables par période. Alimente le bandeau
de synthèse en haut de la page Paiements.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps_coop.payments.models import Payment
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

STATS = "/api/v1/payments/admin/stats/"


@pytest.fixture
def active_member(db):
    """Membre actif SANS carnet — ce module compte EXACTEMENT les paiements
    fabriqués par le test (la fixture partagée ajoute un Payment frais_carnet
    validé qui fausserait les compteurs)."""
    return MemberFactory(with_carnet=False)


def _pay(member, *, montant, type_, statut, frais="0", when=None):
    return Payment.objects.create(
        member=member,
        montant=Decimal(montant),
        frais_transaction=Decimal(frais),
        type=type_,
        source=Payment.Source.MANUEL,
        statut=statut,
        idempotency_key=uuid.uuid4(),
        date_versement=when or timezone.now(),
    )


@pytest.fixture
def seeded_payments(active_member):
    now = timezone.now()
    old = now - timedelta(days=40)
    # Aujourd'hui : 2 validés (épargne 10000 + collecte 5000, frais 200), 1 attente.
    _pay(active_member, montant="10000", type_=Payment.Type.EPARGNE_CLASSIQUE,
         statut=Payment.Statut.VALIDE, when=now)
    _pay(active_member, montant="5000", type_=Payment.Type.EPARGNE,
         statut=Payment.Statut.VALIDE, frais="200", when=now)
    _pay(active_member, montant="3000", type_=Payment.Type.EPARGNE,
         statut=Payment.Statut.EN_ATTENTE, when=now)
    # Il y a 40 jours : 1 validé (remboursement 20000) + 1 rejeté.
    _pay(active_member, montant="20000", type_=Payment.Type.REMBOURSEMENT,
         statut=Payment.Statut.VALIDE, when=old)
    _pay(active_member, montant="50000", type_=Payment.Type.EPARGNE_CLASSIQUE,
         statut=Payment.Statut.REJETE, when=old)
    return now, old


def _admin(admin_user):
    c = APIClient()
    c.force_authenticate(admin_user)
    return c


class TestPaymentsStats:
    def test_requires_staff(self, active_member, seeded_payments):
        r = APIClient().get(STATS)
        assert r.status_code in (401, 403)

    def test_global_totals_without_period(self, admin_user, seeded_payments):
        r = _admin(admin_user).get(STATS)
        assert r.status_code == 200, r.content
        body = r.json()
        # Validés = 10000 + 5000 + 20000 = 35000 ; frais = 200.
        assert Decimal(body["valides"]["montant"]) == Decimal("35000")
        assert body["valides"]["count"] == 3
        assert Decimal(body["valides"]["frais"]) == Decimal("200")
        assert Decimal(body["valides"]["total_paye"]) == Decimal("35200")
        assert Decimal(body["en_attente"]["montant"]) == Decimal("3000")
        assert Decimal(body["rejetes"]["montant"]) == Decimal("50000")

    def test_par_type_breakdown_validated_only(self, admin_user, seeded_payments):
        body = _admin(admin_user).get(STATS).json()
        by_type = {r["type"]: Decimal(r["montant"]) for r in body["par_type"]}
        assert by_type["remboursement"] == Decimal("20000")
        assert by_type["epargne_classique"] == Decimal("10000")
        assert by_type["epargne"] == Decimal("5000")
        # Le rejeté (epargne_classique 50000) n'est PAS dans par_type.

    def test_period_filter_today_only(self, admin_user, seeded_payments):
        now, _ = seeded_payments
        today = now.date().isoformat()
        body = _admin(admin_user).get(
            f"{STATS}?date_from={today}&date_to={today}"
        ).json()
        # Seuls les paiements du jour : validés 10000 + 5000 = 15000.
        assert Decimal(body["valides"]["montant"]) == Decimal("15000")
        assert body["valides"]["count"] == 2
        assert Decimal(body["rejetes"]["montant"]) == Decimal("0")
        assert body["period"]["from"] == today

    def test_type_filter(self, admin_user, seeded_payments):
        body = _admin(admin_user).get(
            f"{STATS}?type=epargne_classique"
        ).json()
        # Validés epargne_classique = 10000 ; le rejeté (50000) va dans rejetes.
        assert Decimal(body["valides"]["montant"]) == Decimal("10000")
        assert Decimal(body["rejetes"]["montant"]) == Decimal("50000")
