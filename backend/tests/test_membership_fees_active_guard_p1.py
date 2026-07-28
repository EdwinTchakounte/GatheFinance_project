"""P1 — un compte DÉJÀ ACTIF ne doit plus se voir réclamer / payer les frais d'adhésion.

Symptôme corrigé : un membre actif (activation terminée) revoyait les 3 frais
comme dus et pouvait les re-régler, car l'état « payé » ne dépendait que de la
présence de lignes Payment (absentes pour les comptes activés autrement / migrés).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.members.fee_from_savings_services import (
    FeePaymentError,
    pay_membership_fee_from_savings,
)
from apps_coop.members.models import Member
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount

pytestmark = pytest.mark.django_db


def _seed_fees():
    for code, montant in (("ADHESION", "10000"), ("INSCRIPTION", "2000"), ("CARNET", "1000")):
        FeeType.objects.update_or_create(
            code=code, defaults={"montant": Decimal(montant), "actif": True, "libelle": code}
        )


def test_active_member_sees_all_fees_paid(active_member):
    _seed_fees()
    client = APIClient()
    client.force_authenticate(user=active_member.user)
    r = client.get("/api/v1/me/fees/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["statut"] == Member.Statut.ACTIF
    for code in ("ADHESION", "INSCRIPTION", "CARNET"):
        assert body["fees"][code]["paye"] is True
        assert body["fees"][code]["solvable"] is False


def test_active_member_cannot_repay_fee(active_member):
    _seed_fees()
    # Épargne largement suffisante — le blocage doit venir du statut ACTIF.
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("50000"), date_ouverture=date.today()
    )
    with pytest.raises(FeePaymentError):
        pay_membership_fee_from_savings(active_member, "ADHESION")


def test_non_active_member_can_still_pay(active_member):
    """Un membre NON actif (ex. réactivation post-clôture) garde le droit de payer."""
    _seed_fees()
    active_member.statut = Member.Statut.SUSPENDU
    active_member.save(update_fields=["statut"])
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("50000"), date_ouverture=date.today()
    )
    payment = pay_membership_fee_from_savings(active_member, "ADHESION")
    assert payment.montant == Decimal("10000")
