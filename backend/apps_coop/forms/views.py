"""API REST du moteur FormSchema (CH-4).

Endpoints :
  Public (anonyme accepté pour l'adhésion uniquement ; auth pour les autres) :
    GET  /forms/schemas/{kind}/active/  → schéma actif pour ce kind

  Admin (staff) :
    GET    /forms/admin/schemas/                  → liste paginée (filtres)
    POST   /forms/admin/schemas/                  → nouvelle version
    GET    /forms/admin/schemas/{id}/             → détail
    PATCH  /forms/admin/schemas/{id}/             → update brouillon
    DELETE /forms/admin/schemas/{id}/             → supprime un brouillon (interdit sur actif)
    POST   /forms/admin/schemas/{id}/activate/    → bascule en actif (désactive l'ancien)
    POST   /forms/admin/schemas/{id}/duplicate/   → duplique en nouvelle version brouillon
"""
from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import record as record_audit

from .models import FormSchema
from .serializers import (
    FormSchemaAdminSerializer,
    FormSchemaPublicSerializer,
)


# ----------------------------------------------------------------------
# Endpoint public — schéma actif par kind.
# ----------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def public_active_schema(request, kind: str):
    """Retourne le schéma actif pour un kind donné.

    Accessible anonymement — l'adhésion est un formulaire public, et les
    autres formulaires sont protégés par leur propre endpoint POST de
    soumission (auth requis là).
    """
    if kind not in FormSchema.Kind.values:
        return Response({"detail": f"kind {kind!r} inconnu."}, status=400)
    schema = FormSchema.objects.filter(kind=kind, is_active=True).first()
    if schema is None:
        return Response(
            {"detail": f"Aucun schéma actif pour {kind!r}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(FormSchemaPublicSerializer(schema).data)


# ----------------------------------------------------------------------
# Admin CRUD.
# ----------------------------------------------------------------------
class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


@api_view(["GET", "POST"])
@permission_classes([IsStaff])
def admin_schema_list(request):
    if request.method == "GET":
        qs = FormSchema.objects.all().order_by("kind", "-version")
        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        return Response(FormSchemaAdminSerializer(qs, many=True).data)

    # POST — nouvelle version (brouillon).
    serializer = FormSchemaAdminSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    kind = serializer.validated_data["kind"]
    next_version = (
        (FormSchema.objects.filter(kind=kind).order_by("-version").values_list("version", flat=True).first() or 0)
        + 1
    )
    serializer.validated_data["version"] = next_version
    schema = FormSchema.objects.create(
        kind=kind,
        version=next_version,
        title=serializer.validated_data["title"],
        description=serializer.validated_data.get("description", ""),
        schema=serializer.validated_data["schema"],
        notes_admin=serializer.validated_data.get("notes_admin", ""),
        created_by=request.user,
        is_active=False,
    )
    record_audit(
        action="form_schema.created",
        entite_type="FormSchema",
        entite_id=schema.id,
        user=request.user,
        details={"kind": kind, "version": next_version},
    )
    return Response(FormSchemaAdminSerializer(schema).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsStaff])
def admin_schema_detail(request, pk: int):
    schema = get_object_or_404(FormSchema, pk=pk)
    if request.method == "GET":
        return Response(FormSchemaAdminSerializer(schema).data)

    if request.method == "DELETE":
        if schema.is_active:
            return Response(
                {"detail": "Impossible de supprimer un schéma actif."},
                status=400,
            )
        record_audit(
            action="form_schema.deleted",
            entite_type="FormSchema",
            entite_id=schema.id,
            user=request.user,
            details={"kind": schema.kind, "version": schema.version},
        )
        schema.delete()
        return Response(status=204)

    # PATCH — édition d'un brouillon. Les champs structurants (kind, version)
    # sont figés.
    if schema.is_active:
        return Response(
            {"detail": "Crée une nouvelle version pour modifier ; le schéma actif est gelé."},
            status=400,
        )
    serializer = FormSchemaAdminSerializer(schema, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    for field in ("title", "description", "schema", "notes_admin"):
        if field in serializer.validated_data:
            setattr(schema, field, serializer.validated_data[field])
    schema.save()
    record_audit(
        action="form_schema.updated",
        entite_type="FormSchema",
        entite_id=schema.id,
        user=request.user,
        details={"kind": schema.kind, "version": schema.version},
    )
    return Response(FormSchemaAdminSerializer(schema).data)


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_schema_activate(request, pk: int):
    """Active une version (et désactive l'ancien actif du même kind)."""
    schema = get_object_or_404(FormSchema, pk=pk)
    if schema.is_active:
        return Response({"detail": "Déjà actif."}, status=400)

    with transaction.atomic():
        # Désactive l'actif courant éventuel (contrainte partielle unique
        # impose qu'il n'y en ait qu'un).
        FormSchema.objects.filter(kind=schema.kind, is_active=True).update(
            is_active=False,
        )
        schema.is_active = True
        schema.activated_at = timezone.now()
        schema.activated_by = request.user
        schema.save(update_fields=["is_active", "activated_at", "activated_by", "updated_at"])

    record_audit(
        action="form_schema.activated",
        entite_type="FormSchema",
        entite_id=schema.id,
        user=request.user,
        details={"kind": schema.kind, "version": schema.version},
    )
    return Response(FormSchemaAdminSerializer(schema).data)


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_schema_duplicate(request, pk: int):
    """Duplique un schéma en nouvelle version brouillon (clone du JSON)."""
    src = get_object_or_404(FormSchema, pk=pk)
    next_version = (
        FormSchema.objects.filter(kind=src.kind).order_by("-version").values_list("version", flat=True).first()
        or 0
    ) + 1
    clone = FormSchema.objects.create(
        kind=src.kind,
        version=next_version,
        title=src.title,
        description=src.description,
        schema=src.schema,
        notes_admin=f"Dupliqué depuis v{src.version}.",
        created_by=request.user,
        is_active=False,
    )
    record_audit(
        action="form_schema.duplicated",
        entite_type="FormSchema",
        entite_id=clone.id,
        user=request.user,
        details={"kind": src.kind, "from_version": src.version, "to_version": next_version},
    )
    return Response(FormSchemaAdminSerializer(clone).data, status=201)
