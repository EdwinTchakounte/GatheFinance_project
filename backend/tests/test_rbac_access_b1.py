"""Lot B (RBAC) — résolution d'accès + endpoints staff/rôles.

Règles testées (voir apps_coop/members/access.py) :
  * superuser / groupe admin              → accès total
  * staff/comité legacy sans rôle         → accès total (rétro-compat)
  * staff avec rôle(s)                     → union des ressources (restreint)
  * utilisateur sans groupe               → aucun accès
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.members.access import (
    effective_resources,
    has_full_access,
    staff_has_resource,
)
from apps_coop.members.models import StaffRole
from apps_coop.members.resources import RESOURCE_KEYS

pytestmark = pytest.mark.django_db

User = get_user_model()


def _user(email, *, superuser=False, group=None):
    u = User.objects.create_user(
        username=email, email=email, password="pass12345", is_staff=True,
        is_superuser=superuser,
    )
    if group:
        g, _ = Group.objects.get_or_create(name=group)
        u.groups.add(g)
    return u


def _client(user):
    c = APIClient()
    c.force_login(user)
    return c


# --------------------------------------------------------------------------- #
# Résolution d'accès
# --------------------------------------------------------------------------- #
class TestEffectiveResources:
    def test_superuser_has_everything(self):
        u = _user("su@t.local", superuser=True)
        assert effective_resources(u) == set(RESOURCE_KEYS)
        assert has_full_access(u) is True

    def test_admin_group_has_everything(self):
        u = _user("a@t.local", group="admin")
        assert effective_resources(u) == set(RESOURCE_KEYS)
        assert has_full_access(u) is True

    def test_legacy_staff_without_role_is_full(self):
        u = _user("s@t.local", group="staff")
        assert effective_resources(u) == set(RESOURCE_KEYS)
        assert has_full_access(u) is True

    def test_staff_with_role_is_restricted(self):
        u = _user("carnet@t.local", group="staff")
        role = StaffRole.objects.create(
            name="Gestionnaire carnets", resources=["booklet-orders", "members"]
        )
        role.users.add(u)
        assert effective_resources(u) == {"booklet-orders", "members"}
        assert has_full_access(u) is False
        assert staff_has_resource(u, "booklet-orders") is True
        assert staff_has_resource(u, "loans") is False

    def test_multiple_roles_union(self):
        u = _user("multi@t.local", group="staff")
        r1 = StaffRole.objects.create(name="R1", resources=["booklet-orders"])
        r2 = StaffRole.objects.create(name="R2", resources=["payments", "costs"])
        r1.users.add(u)
        r2.users.add(u)
        assert effective_resources(u) == {"booklet-orders", "payments", "costs"}

    def test_user_without_group_has_nothing(self):
        u = User.objects.create_user(username="x@t.local", email="x@t.local", password="p12345678")
        assert effective_resources(u) == set()
        assert has_full_access(u) is False


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
class TestAccessEndpoints:
    def test_me_exposes_resources(self):
        u = _user("carnet2@t.local", group="staff")
        role = StaffRole.objects.create(name="Carnets", resources=["booklet-orders"])
        role.users.add(u)
        res = _client(u).get("/api/v1/auth/me/")
        assert res.status_code == 200
        assert res.data["resources"] == ["booklet-orders"]
        assert res.data["full_access"] is False

    def test_admin_creates_role_and_user(self):
        admin = _user("boss@t.local", superuser=True)
        c = _client(admin)

        # Créer un rôle.
        r = c.post(
            "/api/v1/admin/access/roles/",
            {"name": "Caissier", "resources": ["payments", "withdrawals", "nope"]},
            format="json",
        )
        assert r.status_code == 201, r.data
        assert r.data["resources"] == ["payments", "withdrawals"]  # "nope" filtré
        role_id = r.data["id"]

        # Créer un utilisateur staff avec ce rôle.
        u = c.post(
            "/api/v1/admin/access/users/",
            {"email": "New@T.Local", "first_name": "Awa", "role_ids": [role_id]},
            format="json",
        )
        assert u.status_code == 201, u.data
        assert u.data["email"] == "new@t.local"
        assert u.data["resources"] == ["payments", "withdrawals"]
        assert "temporary_password" in u.data  # généré, montré une fois

        # Le nouvel utilisateur peut se connecter et voit ses ressources.
        new_user = User.objects.get(email="new@t.local")
        assert new_user.check_password(u.data["temporary_password"])

    def test_restricted_user_cannot_reach_access_module(self):
        u = _user("caissier@t.local", group="staff")
        role = StaffRole.objects.create(name="Caisse", resources=["payments"])
        role.users.add(u)
        res = _client(u).get("/api/v1/admin/access/users/")
        assert res.status_code == 403

    def test_duplicate_email_rejected(self):
        admin = _user("boss2@t.local", superuser=True)
        c = _client(admin)
        c.post("/api/v1/admin/access/users/", {"email": "dup@t.local"}, format="json")
        again = c.post("/api/v1/admin/access/users/", {"email": "dup@t.local"}, format="json")
        assert again.status_code == 400
