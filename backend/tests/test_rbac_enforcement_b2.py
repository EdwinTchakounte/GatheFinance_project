"""Lot B (RBAC) — enforcement backend via RBACResourceMiddleware.

On utilise ``force_login`` (session réelle) pour que ``request.user`` soit
résolu par l'AuthenticationMiddleware — ``force_authenticate`` (DRF) ne
passerait pas par le middleware.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.members.models import StaffRole

pytestmark = pytest.mark.django_db

User = get_user_model()


def _staff(email, *, superuser=False, roles=None):
    u = User.objects.create_user(
        username=email, email=email, password="pass12345",
        is_staff=True, is_superuser=superuser,
    )
    grp, _ = Group.objects.get_or_create(name="staff")
    u.groups.add(grp)
    if roles:
        for name, resources in roles:
            r = StaffRole.objects.create(name=name, resources=resources)
            r.users.add(u)
    return u


def _client(user):
    c = APIClient()
    c.force_login(user)
    return c


class TestMiddlewareEnforcement:
    def test_restricted_user_reaches_granted_resource(self):
        u = _staff("carnet@t.local", roles=[("Carnets", ["booklet-orders"])])
        res = _client(u).get("/api/v1/admin/booklet-orders/")
        # Autorisé par le middleware → la vue répond (pas de 403 RBAC).
        assert res.status_code != 403

    def test_restricted_user_blocked_on_other_resource(self):
        u = _staff("carnet2@t.local", roles=[("Carnets", ["booklet-orders"])])
        # Ressource "members" non accordée → 403 du middleware.
        assert _client(u).get("/api/v1/admin/members/").status_code == 403
        # Ressource "loans" non accordée → 403.
        assert _client(u).get("/api/v1/loans/admin/loans/").status_code == 403

    def test_superuser_bypasses_everything(self):
        u = _staff("su@t.local", superuser=True)
        assert _client(u).get("/api/v1/loans/admin/loans/").status_code != 403
        assert _client(u).get("/api/v1/admin/members/").status_code != 403

    def test_legacy_staff_without_role_bypasses(self):
        # staff sans rôle = full access legacy → jamais bloqué.
        u = _staff("legacy@t.local")
        assert _client(u).get("/api/v1/admin/members/").status_code != 403

    def test_costs_resource_maps_to_payments_config(self):
        u = _staff("compta@t.local", roles=[("Compta", ["costs"])])
        # config coûts accordée…
        assert _client(u).get("/api/v1/payments/admin/config/").status_code != 403
        # …mais pas les paiements bruts.
        assert _client(u).get("/api/v1/payments/admin/cash-in/").status_code == 403

    def test_non_admin_endpoint_not_guarded(self):
        u = _staff("who@t.local", roles=[("X", ["booklet-orders"])])
        # /auth/me/ n'est pas un endpoint admin → jamais bloqué par le RBAC.
        assert _client(u).get("/api/v1/auth/me/").status_code == 200

    def test_renewals_resource_reaches_savings_admin(self):
        # Correctif : savings/admin/renewals/ mappé sur la ressource "renewals".
        u = _staff("epargne@t.local", roles=[("Epargne", ["renewals"])])
        assert _client(u).get("/api/v1/savings/admin/renewals/").status_code != 403
        # sans la ressource → 403.
        v = _staff("nope@t.local", roles=[("X", ["booklet-orders"])])
        assert _client(v).get("/api/v1/savings/admin/renewals/").status_code == 403


class TestResolveMapping:
    """Vérifie la table de correspondance préfixe/regex → ressource."""

    def test_escalation_open_maps_to_escalations_not_loans(self):
        from apps_coop.members.rbac_middleware import _resolve

        assert _resolve("loans/admin/loans/42/escalation/") == (True, "escalations")
        # Le reste de loans/admin/loans/ reste "loans".
        assert _resolve("loans/admin/loans/42/detail/") == (True, "loans")

    def test_savings_admin_maps_to_renewals(self):
        from apps_coop.members.rbac_middleware import _resolve

        assert _resolve("savings/admin/renewals/") == (True, "renewals")
        assert _resolve("savings/admin/cron/monthly-interest/") == (True, "renewals")


class TestPrivilegeEscalation:
    def test_delegate_cannot_create_admin_group_user(self):
        # Délégué : staff + rôle "access" (peut gérer users) mais PAS full-access.
        deleg = _staff("deleg@t.local", roles=[("UserMgr", ["access"])])
        res = _client(deleg).post(
            "/api/v1/admin/access/users/",
            {"email": "boss@t.local", "group": "admin"},
            format="json",
        )
        assert res.status_code == 403
        assert not User.objects.filter(email="boss@t.local").exists()

    def test_delegate_cannot_self_promote_to_admin(self):
        deleg = _staff("deleg2@t.local", roles=[("UserMgr", ["access"])])
        res = _client(deleg).patch(
            f"/api/v1/admin/access/users/{deleg.id}/",
            {"group": "admin"},
            format="json",
        )
        assert res.status_code == 403

    def test_superuser_can_create_admin_group_user(self):
        su = _staff("root@t.local", superuser=True)
        res = _client(su).post(
            "/api/v1/admin/access/users/",
            {"email": "newadmin@t.local", "group": "admin"},
            format="json",
        )
        assert res.status_code == 201

    def test_delegate_can_still_create_staff_user(self):
        deleg = _staff("deleg3@t.local", roles=[("UserMgr", ["access"])])
        res = _client(deleg).post(
            "/api/v1/admin/access/users/",
            {"email": "agent@t.local", "group": "staff"},
            format="json",
        )
        assert res.status_code == 201


class TestLoanStaffEndpointsGuarded:
    """field-visit / evaluate-guarantee (hors /admin/) exigent loan-requests."""

    def test_restricted_staff_blocked_without_loan_requests(self):
        u = _staff("carnet3@t.local", roles=[("Carnets", ["booklet-orders"])])
        assert (
            _client(u).post("/api/v1/loans/requests/1/field-visit/").status_code == 403
        )
        assert (
            _client(u).post("/api/v1/loans/requests/1/evaluate-guarantee/").status_code
            == 403
        )

    def test_with_loan_requests_not_403(self):
        u = _staff("credit@t.local", roles=[("Credit", ["loan-requests"])])
        # Pas de crédit #1 → 404/400, mais surtout PAS 403 (accès autorisé).
        assert (
            _client(u).post("/api/v1/loans/requests/1/field-visit/").status_code != 403
        )


class TestAntidatedEntriesGuarded:
    """Saisies antidatées : mappées sur `antidated-entries`, PAS `renewals`.

    Le catch-all `savings/admin/` → `renewals` capturerait ces URLs si les
    règles spécifiques n'étaient pas placées avant lui. On vérifie donc que le
    routage RBAC discrimine bien les deux ressources.
    """

    URL_BOOKLET = "/api/v1/savings/admin/antidated-booklet/"
    URL_ENTRY = "/api/v1/savings/admin/antidated-entry/"

    def test_granted_resource_reaches_endpoints(self):
        u = _staff("anti@t.local", roles=[("Repro", ["antidated-entries"])])
        # Accès autorisé → la vue répond (400 corps vide, mais surtout pas 403).
        assert _client(u).post(self.URL_BOOKLET).status_code != 403
        assert _client(u).post(self.URL_ENTRY).status_code != 403

    def test_renewals_role_does_not_grant_antidated(self):
        u = _staff("renew@t.local", roles=[("Renew", ["renewals"])])
        # `renewals` ne doit PAS ouvrir les saisies antidatées (sinon le
        # catch-all les aurait avalées sous la mauvaise ressource).
        assert _client(u).post(self.URL_BOOKLET).status_code == 403
        assert _client(u).post(self.URL_ENTRY).status_code == 403

    def test_antidated_role_does_not_grant_renewals(self):
        u = _staff("anti2@t.local", roles=[("Repro", ["antidated-entries"])])
        # …et réciproquement : la ressource dédiée n'ouvre pas les renewals.
        assert (
            _client(u).get("/api/v1/savings/admin/renewals/").status_code == 403
        )
