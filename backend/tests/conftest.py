"""Shared fixtures for the GATHE Finance test-suite.

Tous les tests qui touchent la DB doivent demander la fixture pytest-django
``db`` (ou ``transactional_db`` si on a besoin d'un vrai commit, par ex. pour
tester ``select_for_update``). Les factories vivent dans ``tests/factories.py``.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """Vide le cache (config helpers) entre chaque test.

    Le cache LocMem n'est pas rollback avec la transaction DB : sans ce reset,
    une valeur AppSetting/RateParam mémoïsée fuiterait d'un test à l'autre.
    """
    cache.clear()
    yield
    cache.clear()

from tests.factories import (
    MemberFactory,
    MembershipRequestFactory,
    SuspendedMemberFactory,
)


@pytest.fixture
def staff_user(db):
    """Compte staff (is_staff=True) — utilisé pour tester les endpoints admin."""
    User = get_user_model()
    user = User.objects.create_user(
        username="staff@test.local",
        email="staff@test.local",
        password="testpass1234",
        is_staff=True,
    )
    Group.objects.get_or_create(name="staff")
    return user


@pytest.fixture
def admin_user(db):
    """Compte admin coopératif — staff + groupe `coop_admin`."""
    User = get_user_model()
    user = User.objects.create_user(
        username="admin@test.local",
        email="admin@test.local",
        password="testpass1234",
        is_staff=True,
        is_superuser=True,
    )
    coop_admin, _ = Group.objects.get_or_create(name="coop_admin")
    user.groups.add(coop_admin)
    return user


@pytest.fixture
def pending_request(db):
    """Une `MembershipRequest` en attente prête à être approuvée/rejetée."""
    return MembershipRequestFactory()


@pytest.fixture
def active_member(db):
    """Un membre `actif` avec son `SavingsAccount` à zéro."""
    return MemberFactory()


@pytest.fixture
def suspended_member(db):
    """Un membre `suspendu` qui n'a pas encore payé sa 1re cotisation."""
    return SuspendedMemberFactory()


@pytest.fixture
def tara_payout_on(db):
    """Active le payout Tara initié par la plateforme (désactivé par défaut
    depuis le passage au « payout manuel » : décaissement/retrait faits sur
    Tara par l'admin puis marqués « payé »)."""
    from apps_coop.audit.models import AppSetting

    AppSetting.objects.update_or_create(
        cle="payments.tara_payout.enabled",
        defaults={"valeur": "true", "description": ""},
    )
    return True
