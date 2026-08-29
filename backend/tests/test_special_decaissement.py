"""Décaissement d'une participation caisse/tontine (retrait du solde).

Chaque compte de collecte particulière doit pouvoir subir un retrait qui sort
réellement l'argent — vers l'épargne classique du membre OU en espèces (agence).
"""
from datetime import date
from decimal import Decimal

import pytest

from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.special_collections.models import (
    SpecialCollectionCycle,
    SpecialCollectionMembership,
    SpecialCollectionTransaction,
)
from apps_coop.special_collections.services import (
    SpecialCollectionError,
    decaisser_participation,
)

pytestmark = pytest.mark.django_db


def _cycle_and_membership(member):
    cycle = SpecialCollectionCycle.objects.create(
        type="caisse_scolaire",
        nom="Caisse test",
        montant_minimal=Decimal("1000"),
        date_debut=date(2026, 1, 1),
    )
    m = SpecialCollectionMembership.objects.create(
        member=member,
        cycle=cycle,
        statut=SpecialCollectionMembership.Statut.VALIDE,
        solde=Decimal("50000"),
    )
    return cycle, m


def test_decaissement_vers_epargne(active_member):
    cycle, m = _cycle_and_membership(active_member)
    acc, _ = ClassicSavingsAccount.objects.get_or_create(
        member=active_member, defaults={"solde": Decimal("0"), "date_ouverture": date(2026, 1, 1)}
    )
    ep0 = Decimal(acc.solde)

    row = decaisser_participation(
        member=active_member, cycle_id=cycle.id, montant=Decimal("30000"),
        destination="epargne",
    )

    m.refresh_from_db()
    acc.refresh_from_db()
    assert m.solde == Decimal("20000")  # solde débité
    assert Decimal(acc.solde) == ep0 + Decimal("30000")  # épargne créditée
    assert row.type_op == SpecialCollectionTransaction.TypeOp.RETRAIT


def test_decaissement_cash_ne_credite_pas_epargne(active_member):
    cycle, m = _cycle_and_membership(active_member)
    acc, _ = ClassicSavingsAccount.objects.get_or_create(
        member=active_member, defaults={"solde": Decimal("0"), "date_ouverture": date(2026, 1, 1)}
    )
    ep0 = Decimal(acc.solde)

    decaisser_participation(
        member=active_member, cycle_id=cycle.id, montant=Decimal("10000"),
        destination="cash",
    )

    m.refresh_from_db()
    acc.refresh_from_db()
    assert m.solde == Decimal("40000")
    assert Decimal(acc.solde) == ep0  # espèces : pas de crédit épargne


def test_decaissement_refuse_montant_superieur_au_solde(active_member):
    cycle, _m = _cycle_and_membership(active_member)
    with pytest.raises(SpecialCollectionError):
        decaisser_participation(
            member=active_member, cycle_id=cycle.id, montant=Decimal("999999"),
            destination="cash",
        )


def test_decaissement_admin_endpoint(admin_client, active_member):
    cycle, m = _cycle_and_membership(active_member)
    resp = admin_client.post(
        f"/api/v1/special-collections/admin/{m.id}/decaisser/",
        data={"montant": 25000, "destination": "epargne"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    m.refresh_from_db()
    assert m.solde == Decimal("25000")
