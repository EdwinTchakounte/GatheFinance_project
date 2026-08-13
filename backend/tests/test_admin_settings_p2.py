"""Tests P2 — Endpoints admin AppSettings (refonte 2026 tunables).

Couvre :
  * ``GET /audit/admin/settings/`` — catalogue + valeurs courantes + groupes.
  * ``PATCH /audit/admin/settings/<key>/`` — édition + validation par type.
  * 404 sur clé inconnue, 400 sur valeur invalide, 403 sur non-staff.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting, AuditLog


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def staff_client(staff_user):
    from django.contrib.auth.models import Group

    grp, _ = Group.objects.get_or_create(name="staff")
    staff_user.groups.add(grp)
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def member_client(active_member):
    client = APIClient()
    client.force_authenticate(user=active_member.user)
    return client


# ---------------------------------------------------------------------------
# GET /audit/admin/settings/
# ---------------------------------------------------------------------------


class TestList:
    def test_returns_catalog_and_groups(self, staff_client):
        r = staff_client.get("/api/v1/audit/admin/settings/")
        assert r.status_code == 200
        data = r.json()
        assert "groups" in data and "settings" in data
        assert len(data["groups"]) >= 10
        assert len(data["settings"]) >= 30

    def test_uses_default_if_not_in_db(self, staff_client):
        # On supprime tous les AppSettings pour vérifier le fallback default.
        AppSetting.objects.all().delete()
        r = staff_client.get("/api/v1/audit/admin/settings/")
        keys = {s["key"]: s for s in r.json()["settings"]}
        assert keys["seniority.threshold_months"]["value"] == "12"
        assert keys["seniority.threshold_months"]["is_admin_edited"] is False

    def test_reflects_db_value(self, staff_client):
        AppSetting.objects.update_or_create(
            cle="seniority.threshold_months",
            defaults={"valeur": "24"},
        )
        r = staff_client.get("/api/v1/audit/admin/settings/")
        keys = {s["key"]: s for s in r.json()["settings"]}
        assert keys["seniority.threshold_months"]["value"] == "24"
        assert keys["seniority.threshold_months"]["is_admin_edited"] is True

    def test_includes_type_metadata(self, staff_client):
        r = staff_client.get("/api/v1/audit/admin/settings/")
        keys = {s["key"]: s for s in r.json()["settings"]}
        # enum doit exposer 'choices'.
        mode = keys["loans.judicial_escalation.mode"]
        assert mode["type"] == "enum"
        assert "manual" in mode["choices"]
        assert "auto" in mode["choices"]
        # decimal doit exposer min/max.
        rate = keys["loans.lender.interest_rate"]
        assert rate["type"] == "decimal"
        assert rate["min"] == 0 and rate["max"] == 1
        # Le réglage legacy obsolète est masqué de la liste (hidden).
        assert "lender.interest_share_rate" not in keys

    def test_forbidden_for_non_staff(self, member_client):
        r = member_client.get("/api/v1/audit/admin/settings/")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /audit/admin/settings/<key>/
# ---------------------------------------------------------------------------


class TestPatch:
    def test_update_int_setting(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/seniority.threshold_months/",
            {"value": 18},
            format="json",
        )
        assert r.status_code == 200, r.content
        assert r.json()["value"] == "18"
        # Vérifie persistance.
        assert AppSetting.objects.get(cle="seniority.threshold_months").valeur == "18"

    def test_update_bool_accepts_python_bool(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/loans.eligibility.allow_avaliste/",
            {"value": False},
            format="json",
        )
        assert r.status_code == 200
        assert r.json()["value"] == "false"

    def test_update_decimal_clamps(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/lender.interest_share_rate/",
            {"value": "1.5"},  # > 1, doit échouer
            format="json",
        )
        assert r.status_code == 400
        assert "≤" in r.json()["detail"]

    def test_update_enum_invalid_choice(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/loans.judicial_escalation.mode/",
            {"value": "bogus"},
            format="json",
        )
        assert r.status_code == 400
        assert "Doit être l'une de" in r.json()["detail"]

    def test_update_enum_valid_choice(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/loans.judicial_escalation.mode/",
            {"value": "hybrid"},
            format="json",
        )
        assert r.status_code == 200
        assert r.json()["value"] == "hybrid"

    def test_unknown_key_returns_404(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/totally.fake.key/",
            {"value": "x"},
            format="json",
        )
        assert r.status_code == 404

    def test_missing_value_returns_400(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/seniority.threshold_months/",
            {},
            format="json",
        )
        assert r.status_code == 400

    def test_forbidden_for_non_staff(self, member_client):
        r = member_client.patch(
            "/api/v1/audit/admin/settings/seniority.threshold_months/",
            {"value": 18},
            format="json",
        )
        assert r.status_code == 403

    def test_audit_recorded(self, staff_client):
        staff_client.patch(
            "/api/v1/audit/admin/settings/loans.eligibility.route_priority/",
            {"value": "campaign,senior_brc,avaliste"},
            format="json",
        )
        log = AuditLog.objects.filter(
            action="config.app_setting_updated"
        ).first()
        assert log is not None
        assert log.details_json["key"] == "loans.eligibility.route_priority"
        assert log.details_json["value"] == "campaign,senior_brc,avaliste"

    def test_csv_type_accepts_anything(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/loans.seizure.source_order/",
            {"value": "borrower_collecte,avaliste_collecte"},
            format="json",
        )
        assert r.status_code == 200

    def test_int_min_bound_enforced(self, staff_client):
        r = staff_client.patch(
            "/api/v1/audit/admin/settings/seniority.threshold_months/",
            {"value": -5},
            format="json",
        )
        assert r.status_code == 400
        assert "≥" in r.json()["detail"]


class TestCatalogGroupsIntegrity:
    """Tout groupe utilisé par une entrée du CATALOG doit exister dans
    GROUPS_ORDER, sinon la page admin (qui rend par groupe) laisse tomber
    silencieusement ces réglages — cf. régression apport 2026-07-26."""

    def test_every_catalog_group_is_declared(self):
        from apps_coop.audit.tunables import CATALOG, GROUPS_ORDER

        declared = {key for key, _label in GROUPS_ORDER}
        used = {entry["group"] for entry in CATALOG}
        missing = used - declared
        assert not missing, f"Groupes utilisés mais non déclarés dans GROUPS_ORDER : {missing}"

    def test_apport_settings_are_rendered_by_admin(self, staff_client):
        r = staff_client.get("/api/v1/audit/admin/settings/")
        assert r.status_code == 200
        payload = r.json()
        group_keys = {g["key"] for g in payload["groups"]}
        assert "apport" in group_keys
        setting_keys = {s["key"] for s in payload["settings"]}
        assert "loans.apport.rate" in setting_keys
        assert "loans.apport.min_available_rate" in setting_keys
