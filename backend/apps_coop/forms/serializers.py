"""Serializers pour le moteur FormSchema (CH-4)."""
from __future__ import annotations

from rest_framework import serializers

from .models import FormSchema


_ALLOWED_FIELD_TYPES = {
    "text", "email", "tel", "number", "textarea",
    "select", "radio", "checkbox", "file", "date",
}
_ALLOWED_OPERATORS = {"equals", "not_equals", "in"}


def _collect_fields(schema: dict) -> dict[str, dict]:
    """Renvoie un dict {field_id: field_dict} pour faciliter les comparaisons."""
    out: dict[str, dict] = {}
    for section in (schema or {}).get("sections", []) or []:
        for field in section.get("fields", []) or []:
            fid = field.get("id")
            if fid:
                out[fid] = field
    return out


def _validate_locked_fields_preserved(new_schema: dict, *, kind: str) -> None:
    """Refuse une nouvelle version qui casse les champs verrouillés (CH-4).

    Pour chaque champ ``is_locked: True`` du schéma actif du même ``kind`` :
      - il doit toujours exister dans le nouveau schéma (même ``id``)
      - son ``type`` ne doit pas avoir changé
      - il doit toujours porter ``is_locked: True`` (sinon l'admin pourrait le
        « déverrouiller » puis le supprimer en deux versions)

    Le label, help_text, placeholder, options, required, max_length, etc.
    restent librement modifiables — c'est la cosmétique du champ.
    """
    current = FormSchema.objects.filter(kind=kind, is_active=True).first()
    if current is None:
        # Premier schéma de ce kind — pas de référence à protéger.
        return
    new_fields = _collect_fields(new_schema)
    for fid, old_field in _collect_fields(current.schema).items():
        if not old_field.get("is_locked"):
            continue
        new_field = new_fields.get(fid)
        if new_field is None:
            raise serializers.ValidationError(
                f"Le champ verrouillé {fid!r} ne peut pas être supprimé "
                f"(câblé dans le code).",
            )
        if new_field.get("type") != old_field.get("type"):
            raise serializers.ValidationError(
                f"Le type du champ verrouillé {fid!r} ne peut pas être modifié "
                f"({old_field.get('type')} → {new_field.get('type')}).",
            )
        if not new_field.get("is_locked"):
            raise serializers.ValidationError(
                f"Le flag is_locked du champ {fid!r} ne peut pas être retiré.",
            )


def _validate_schema_structure(schema: dict) -> None:
    """Valide la structure minimale d'un schéma de formulaire.

    Soulève ``ValidationError`` si non conforme. Vérifie :
      - clé ``sections`` présente et liste
      - chaque section a id + title + fields (list)
      - chaque field a id + type ∈ _ALLOWED_FIELD_TYPES + label
      - les conditions référencent des operators connus
      - les ids de field sont uniques globalement
    """
    if not isinstance(schema, dict):
        raise serializers.ValidationError("schema doit être un objet JSON.")
    sections = schema.get("sections")
    if not isinstance(sections, list):
        raise serializers.ValidationError("schema.sections doit être une liste.")

    seen_field_ids: set[str] = set()
    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            raise serializers.ValidationError(f"sections[{idx}] doit être un objet.")
        if not section.get("id"):
            raise serializers.ValidationError(f"sections[{idx}].id manquant.")
        if not section.get("title"):
            raise serializers.ValidationError(f"sections[{idx}].title manquant.")
        fields = section.get("fields")
        if not isinstance(fields, list):
            raise serializers.ValidationError(f"sections[{idx}].fields doit être une liste.")
        for fidx, field in enumerate(fields):
            if not isinstance(field, dict):
                raise serializers.ValidationError(
                    f"sections[{idx}].fields[{fidx}] doit être un objet.",
                )
            fid = field.get("id")
            if not fid:
                raise serializers.ValidationError(
                    f"sections[{idx}].fields[{fidx}].id manquant.",
                )
            if fid in seen_field_ids:
                raise serializers.ValidationError(
                    f"Identifiant de champ dupliqué : {fid!r}.",
                )
            seen_field_ids.add(fid)
            ftype = field.get("type")
            if ftype not in _ALLOWED_FIELD_TYPES:
                raise serializers.ValidationError(
                    f"sections[{idx}].fields[{fidx}].type {ftype!r} non supporté.",
                )
            if not field.get("label"):
                raise serializers.ValidationError(
                    f"sections[{idx}].fields[{fidx}].label manquant.",
                )
            cond = field.get("condition")
            if cond is not None:
                if not isinstance(cond, dict):
                    raise serializers.ValidationError(
                        f"sections[{idx}].fields[{fidx}].condition doit être un objet.",
                    )
                if cond.get("operator") not in _ALLOWED_OPERATORS:
                    raise serializers.ValidationError(
                        f"Operator de condition non supporté : {cond.get('operator')!r}.",
                    )


class FormSchemaPublicSerializer(serializers.ModelSerializer):
    """Vue publique pour ``GET /forms/schemas/{kind}/active/``."""

    class Meta:
        model = FormSchema
        fields = ("id", "kind", "version", "title", "description", "schema")
        read_only_fields = fields


class FormSchemaAdminSerializer(serializers.ModelSerializer):
    """Vue admin (CRUD)."""

    # On déclare `kind` explicitement pour court-circuiter les validators
    # auto-générés depuis ``UniqueConstraint(fields=["kind"], condition=...)``
    # (un constraint partiel n'est PAS une vraie contrainte d'unicité, et c'est
    # la view qui gère la création séquentielle des versions).
    kind = serializers.ChoiceField(choices=FormSchema.Kind.choices)
    version = serializers.IntegerField(read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    activated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FormSchema
        fields = (
            "id", "kind", "kind_display", "version", "title", "description",
            "schema", "is_active", "activated_at", "activated_by_name",
            "notes_admin", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "kind_display", "version", "is_active", "activated_at",
            "activated_by_name", "created_at", "updated_at",
        )

    def get_activated_by_name(self, obj: FormSchema) -> str | None:
        u = obj.activated_by
        return u.get_full_name() or u.username if u else None

    def validate_schema(self, value):
        _validate_schema_structure(value)
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # Vérifie les champs verrouillés *uniquement* en présence d'un kind ET
        # d'un schema dans la requête. À l'UPDATE partial, le kind n'est pas
        # repassé mais l'instance le porte.
        schema = attrs.get("schema")
        if schema is None:
            return attrs
        kind = attrs.get("kind") or (self.instance.kind if self.instance else None)
        if kind:
            _validate_locked_fields_preserved(schema, kind=kind)
        return attrs
