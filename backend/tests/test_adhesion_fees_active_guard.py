"""Garde-fou : un compte DÉJÀ ACTIF ne peut plus payer les frais d'activation.

Régression (tâche #39, ressortie en live 2026-08) : les frais d'adhésion /
inscription — payés une seule fois à l'entrée — repassaient pour des comptes
actifs. `my_membership_fees` disait bien « payé », mais les chemins de PAIEMENT
(init MoMo `payments/init/` + cash-in agence) ne bloquaient pas → le membre
actif pouvait être re-débité pour rien.

Le carnet (FRAIS_CARNET) reste payable pour un actif (commande supplémentaire).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.payments.models import FeeType, Payment
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _seed_fee(code, montant="1000"):
    FeeType.objects.update_or_create(
        code=code, defaults={"libelle": code, "montant": Decimal(montant), "actif": True}
    )


def _member_client(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


@pytest.mark.parametrize("ptype", ["frais_adhesion", "frais_inscription"])
def test_active_member_cannot_init_activation_fee(active_member, ptype):
    _seed_fee(FeeType.Code.ADHESION)
    _seed_fee(FeeType.Code.INSCRIPTION)
    r = _member_client(active_member).post(
        "/api/v1/payments/init/",
        {"type": ptype, "montant": 1000, "phone": "699000000", "network": "MTN"},
        format="json",
    )
    assert r.status_code == 403, r.content
    assert "déjà actif" in r.json()["detail"].lower()
    # Aucun Payment de ce type n'a été créé.
    assert not Payment.objects.filter(member=active_member, type=ptype).exists()


def test_active_member_can_still_pay_carnet(active_member):
    """Le carnet reste payable par un actif (carnet supplémentaire)."""
    _seed_fee(FeeType.Code.CARNET)
    r = _member_client(active_member).post(
        "/api/v1/payments/init/",
        {"type": "frais_carnet", "montant": 1000, "phone": "699000000", "network": "MTN"},
        format="json",
    )
    # Pas de 403 « déjà actif » : le carnet passe (200/201 selon provider off/on).
    assert r.status_code in (200, 201), r.content


def _admin_client():
    User = get_user_model()
    u = User.objects.create(username="admincash", is_staff=True, is_superuser=True)
    grp, _ = Group.objects.get_or_create(name="admin")
    u.groups.add(grp)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


def test_admin_cashin_blocks_activation_fee_for_active_member(active_member):
    _seed_fee(FeeType.Code.ADHESION)
    r = _admin_client().post(
        "/api/v1/payments/admin/cash-in/",
        {"type": "frais_adhesion", "montant": 1000, "member_id": active_member.id},
        format="json",
    )
    assert r.status_code == 400, r.content
    assert "déjà actif" in r.json()["detail"].lower()
