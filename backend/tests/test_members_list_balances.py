"""Recap financier par membre dans la liste admin (soldes globaux).

Vérifie que ``GET /api/v1/admin/members/`` expose, par membre, l'épargne
collecte + libre + placement + total et le crédit en cours.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
from tests.factories import MemberFactory, UserFactory

pytestmark = pytest.mark.django_db


def _staff_client():
    from django.contrib.auth.models import Group

    user = UserFactory(is_staff=True)
    user.groups.add(Group.objects.get_or_create(name="staff")[0])
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def test_members_list_exposes_balances():
    member = MemberFactory()
    # Épargne collecte (SavingsAccount créé par la factory) + libre.
    SavingsAccount.objects.filter(member=member).update(solde=Decimal("12000"))
    ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal("30000"), date_ouverture=date.today()
    )

    resp = _staff_client().get("/api/v1/admin/members/")
    assert resp.status_code == 200, resp.content
    row = next(r for r in resp.data["results"] if r["id"] == member.id)

    assert row["epargne_collecte"] == "12000.00"
    assert row["epargne_classique_libre"] == "30000.00"
    assert row["epargne_placement"] == "0"
    # Total = collecte + libre + placement.
    assert Decimal(row["epargne_total"]) == Decimal("42000.00")
    assert Decimal(row["credit_encours"]) == Decimal("0")
