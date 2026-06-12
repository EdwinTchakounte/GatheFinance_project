"""CH-4 — Moteur de formulaires dynamiques (FormSchema).

Couvre :
  - Le seed des 3 schémas v1 actifs (adhesion, loan_request, loan_renewal)
  - L'endpoint public ``GET /forms/schemas/{kind}/active/``
  - Le CRUD admin + activation + duplication
  - La contrainte « un seul actif par kind »
  - La validation de structure du schéma JSON
"""
from __future__ import annotations

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps_coop.forms.models import FormSchema


pytestmark = pytest.mark.django_db


# Schéma minimal valide réutilisable.
_VALID_SCHEMA = {
    "sections": [
        {
            "id": "main",
            "title": "Section",
            "fields": [
                {"id": "field_one", "type": "text", "label": "Champ"},
            ],
        }
    ]
}


@pytest.fixture
def staff_client(staff_user):
    c = APIClient()
    c.force_authenticate(staff_user)
    return c


@pytest.fixture
def member_client(active_member):
    c = APIClient()
    c.force_authenticate(active_member.user)
    return c


@pytest.fixture
def seeded(db):
    """3 schémas v1 actifs (mimique du seed CLI)."""
    call_command("seed_form_schemas")


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
class TestSeed:
    def test_seed_creates_three_active_schemas(self, seeded):
        kinds = set(
            FormSchema.objects.filter(is_active=True).values_list("kind", flat=True)
        )
        assert kinds == {"adhesion", "loan_request", "loan_renewal"}

    def test_seed_is_idempotent(self, seeded):
        call_command("seed_form_schemas")  # second run
        assert FormSchema.objects.filter(is_active=True).count() == 3


# ---------------------------------------------------------------------------
# Endpoint public
# ---------------------------------------------------------------------------
class TestPublicActiveSchema:
    def test_returns_active_schema_for_known_kind(self, seeded):
        c = APIClient()
        r = c.get("/api/v1/forms/schemas/adhesion/active/")
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "adhesion"
        assert body["version"] == 1
        assert "sections" in body["schema"]

    def test_returns_404_when_no_active(self, db):
        c = APIClient()
        r = c.get("/api/v1/forms/schemas/adhesion/active/")
        assert r.status_code == 404

    def test_returns_400_for_unknown_kind(self, db):
        c = APIClient()
        r = c.get("/api/v1/forms/schemas/inexistant/active/")
        assert r.status_code == 400

    def test_endpoint_is_anonymous_accessible(self, seeded):
        # Pas de force_authenticate — anonyme.
        c = APIClient()
        r = c.get("/api/v1/forms/schemas/adhesion/active/")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Admin CRUD
# ---------------------------------------------------------------------------
class TestAdminCRUD:
    def test_list_requires_staff(self, member_client, seeded):
        r = member_client.get("/api/v1/forms/admin/schemas/")
        assert r.status_code == 403

    def test_staff_list_returns_all_versions(self, staff_client, seeded):
        r = staff_client.get("/api/v1/forms/admin/schemas/")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_filter_by_kind(self, staff_client, seeded):
        r = staff_client.get("/api/v1/forms/admin/schemas/?kind=adhesion")
        assert r.status_code == 200
        kinds = {item["kind"] for item in r.json()}
        assert kinds == {"adhesion"}

    def test_create_new_version_starts_inactive(self, staff_client, seeded):
        # On part du schéma actif pour préserver les champs verrouillés —
        # une « vraie » v2 ne supprime jamais les colonnes câblées.
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {
                "kind": "adhesion",
                "title": "Adhésion v2",
                "schema": active.schema,
                "version": 999,  # ignoré côté serveur
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["version"] == 2  # next version après v1 seedée
        assert body["is_active"] is False

    def test_cannot_delete_active_schema(self, staff_client, seeded):
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        r = staff_client.delete(f"/api/v1/forms/admin/schemas/{active.id}/")
        assert r.status_code == 400

    def test_can_delete_draft(self, staff_client, seeded):
        draft = FormSchema.objects.create(
            kind="adhesion",
            version=99,
            title="Brouillon",
            schema=_VALID_SCHEMA,
            is_active=False,
        )
        r = staff_client.delete(f"/api/v1/forms/admin/schemas/{draft.id}/")
        assert r.status_code == 204
        assert not FormSchema.objects.filter(pk=draft.id).exists()

    def test_cannot_patch_active(self, staff_client, seeded):
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        r = staff_client.patch(
            f"/api/v1/forms/admin/schemas/{active.id}/",
            {"title": "Hacked"},
            format="json",
        )
        assert r.status_code == 400

    def test_can_patch_draft(self, staff_client, seeded):
        draft = FormSchema.objects.create(
            kind="adhesion", version=99, title="x", schema=_VALID_SCHEMA, is_active=False,
        )
        r = staff_client.patch(
            f"/api/v1/forms/admin/schemas/{draft.id}/",
            {"title": "Nouveau titre"},
            format="json",
        )
        assert r.status_code == 200
        draft.refresh_from_db()
        assert draft.title == "Nouveau titre"


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------
class TestActivation:
    def test_activate_deactivates_previous(self, staff_client, seeded):
        v1 = FormSchema.objects.get(kind="adhesion", version=1)
        v2 = FormSchema.objects.create(
            kind="adhesion", version=2, title="v2", schema=_VALID_SCHEMA, is_active=False,
        )
        r = staff_client.post(f"/api/v1/forms/admin/schemas/{v2.id}/activate/")
        assert r.status_code == 200
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_active is False
        assert v2.is_active is True
        assert v2.activated_at is not None

    def test_activate_already_active_returns_400(self, staff_client, seeded):
        v1 = FormSchema.objects.get(kind="adhesion", is_active=True)
        r = staff_client.post(f"/api/v1/forms/admin/schemas/{v1.id}/activate/")
        assert r.status_code == 400

    def test_only_one_active_per_kind_constraint(self, db):
        FormSchema.objects.create(
            kind="adhesion", version=1, title="v1", schema=_VALID_SCHEMA, is_active=True,
        )
        # 2e actif sur le même kind doit lever IntegrityError.
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            FormSchema.objects.create(
                kind="adhesion", version=2, title="v2", schema=_VALID_SCHEMA, is_active=True,
            )


# ---------------------------------------------------------------------------
# Duplication
# ---------------------------------------------------------------------------
class TestDuplicate:
    def test_duplicate_creates_inactive_clone(self, staff_client, seeded):
        v1 = FormSchema.objects.get(kind="adhesion", version=1)
        r = staff_client.post(f"/api/v1/forms/admin/schemas/{v1.id}/duplicate/")
        assert r.status_code == 201
        body = r.json()
        assert body["version"] == 2
        assert body["is_active"] is False
        assert body["schema"] == v1.schema


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class TestSchemaValidation:
    def test_missing_sections_rejected(self, staff_client, db):
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {"kind": "adhesion", "title": "x", "schema": {"foo": "bar"}},
            format="json",
        )
        assert r.status_code == 400

    def test_unknown_field_type_rejected(self, staff_client, db):
        bad = {
            "sections": [{
                "id": "s", "title": "S",
                "fields": [{"id": "f", "type": "matrix", "label": "?"}],
            }],
        }
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {"kind": "adhesion", "title": "x", "schema": bad},
            format="json",
        )
        assert r.status_code == 400

    def test_duplicate_field_ids_rejected(self, staff_client, db):
        bad = {
            "sections": [{
                "id": "s", "title": "S",
                "fields": [
                    {"id": "f", "type": "text", "label": "A"},
                    {"id": "f", "type": "text", "label": "B"},
                ],
            }],
        }
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {"kind": "adhesion", "title": "x", "schema": bad},
            format="json",
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# is_locked — champs câblés en dur, protégés contre la suppression
# ---------------------------------------------------------------------------
class TestLockedFields:
    """Le flag ``is_locked`` empêche l'admin de casser le câblage code."""

    def test_seeded_schema_has_locked_critical_fields(self, seeded):
        """Le seed pose ``is_locked`` sur les champs mappés vers colonnes."""
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        ids = {f["id"]: f for s in active.schema["sections"] for f in s["fields"]}
        # email, phone, name doivent être verrouillés (colonnes hard-codées).
        assert ids["email"].get("is_locked") is True
        assert ids["phone"].get("is_locked") is True
        assert ids["name"].get("is_locked") is True

    def test_cannot_remove_locked_field_in_new_version(self, staff_client, seeded):
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        # Construit un schéma qui omet le champ ``email`` (verrouillé).
        sections = [
            {
                **s,
                "fields": [f for f in s["fields"] if f["id"] != "email"],
            }
            for s in active.schema["sections"]
        ]
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {
                "kind": "adhesion",
                "title": "v2 sans email",
                "schema": {"sections": sections},
            },
            format="json",
        )
        assert r.status_code == 400
        assert b"email" in r.content

    def test_cannot_change_locked_field_type(self, staff_client, seeded):
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        sections = []
        for s in active.schema["sections"]:
            new_fields = []
            for f in s["fields"]:
                if f["id"] == "email":
                    # On tente de transformer email en select.
                    new_fields.append({**f, "type": "select", "options": [{"value": "a", "label": "A"}]})
                else:
                    new_fields.append(f)
            sections.append({**s, "fields": new_fields})
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {
                "kind": "adhesion",
                "title": "v2 type changé",
                "schema": {"sections": sections},
            },
            format="json",
        )
        assert r.status_code == 400
        assert b"email" in r.content

    def test_cannot_unlock_a_locked_field(self, staff_client, seeded):
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        sections = []
        for s in active.schema["sections"]:
            new_fields = []
            for f in s["fields"]:
                if f["id"] == "email":
                    # Retire le flag is_locked — interdit.
                    new_fields.append({**f, "is_locked": False})
                else:
                    new_fields.append(f)
            sections.append({**s, "fields": new_fields})
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {
                "kind": "adhesion",
                "title": "v2 déverrouillé",
                "schema": {"sections": sections},
            },
            format="json",
        )
        assert r.status_code == 400

    def test_can_edit_locked_field_label_or_help(self, staff_client, seeded):
        """L'admin peut ajuster les libellés des champs verrouillés."""
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        sections = []
        for s in active.schema["sections"]:
            new_fields = []
            for f in s["fields"]:
                if f["id"] == "email":
                    new_fields.append({**f, "label": "Votre meilleur e-mail"})
                else:
                    new_fields.append(f)
            sections.append({**s, "fields": new_fields})
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {
                "kind": "adhesion",
                "title": "v2 label tweaké",
                "schema": {"sections": sections},
            },
            format="json",
        )
        assert r.status_code == 201

    def test_can_add_new_unlocked_field_alongside(self, staff_client, seeded):
        """L'admin peut ajouter des champs non verrouillés (le but du moteur)."""
        active = FormSchema.objects.get(kind="adhesion", is_active=True)
        sections = [dict(s) for s in active.schema["sections"]]
        # Ajout d'un champ libre dans la dernière section.
        sections[-1] = {
            **sections[-1],
            "fields": [
                *sections[-1]["fields"],
                {"id": "profession_secondaire", "type": "text", "label": "Profession secondaire"},
            ],
        }
        r = staff_client.post(
            "/api/v1/forms/admin/schemas/",
            {
                "kind": "adhesion",
                "title": "v2 champ ajouté",
                "schema": {"sections": sections},
            },
            format="json",
        )
        assert r.status_code == 201

    def test_duplicate_preserves_locked_flag(self, staff_client, seeded):
        v1 = FormSchema.objects.get(kind="adhesion", version=1)
        r = staff_client.post(f"/api/v1/forms/admin/schemas/{v1.id}/duplicate/")
        assert r.status_code == 201
        clone_id = r.json()["id"]
        clone = FormSchema.objects.get(pk=clone_id)
        ids = {f["id"]: f for s in clone.schema["sections"] for f in s["fields"]}
        assert ids["email"].get("is_locked") is True
