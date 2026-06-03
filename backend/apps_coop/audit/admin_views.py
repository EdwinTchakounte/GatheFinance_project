"""Admin endpoints — AppSetting catalog + édition (refonte 2026 P2).

Expose la liste enrichie (catalog + valeur actuelle) au format
``[{group, key, label, description, type, choices, default, value, is_admin_edited}]``,
et un PATCH pour modifier la valeur d'une clé. Toute mutation est tracée
dans l'audit log (``config.app_setting_updated``).

Routes :

  - ``GET  /api/v1/audit/admin/settings/``
  - ``PATCH /api/v1/audit/admin/settings/<key>/``
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps_coop.members.permissions import IsStaff

from .models import AppSetting
from .services import client_ip, record as record_audit
from .tunables import (
    CATALOG,
    GROUPS_ORDER,
    get_entry,
    is_known_key,
    validate_value,
)


def _serialize_entry(entry: dict, current_value: str, is_admin_edited: bool) -> dict:
    """Combine catalog entry + valeur courante en un dict UI-friendly."""
    payload = {
        "key": entry["key"],
        "group": entry["group"],
        "label": entry["label"],
        "description": entry["description"],
        "type": entry["type"],
        "default": entry["default"],
        "value": current_value,
        "is_admin_edited": is_admin_edited,
    }
    for opt in ("choices", "min", "max"):
        if opt in entry:
            payload[opt] = entry[opt]
    return payload


@extend_schema(
    tags=["audit"],
    summary="Liste des AppSettings tunables (admin)",
    description=(
        "Renvoie le catalogue complet des paramètres système admin-éditables "
        "(refonte 2026), enrichi de la valeur actuelle en base. Si une clé "
        "n'a jamais été touchée, ``value == default`` et ``is_admin_edited "
        "== false``."
    ),
    responses={200: OpenApiResponse(description="`{ groups, settings }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_settings_list(request):
    """Liste enrichie + groupes (ordonnés)."""
    db_values = {
        s.cle: s.valeur
        for s in AppSetting.objects.filter(
            cle__in=[e["key"] for e in CATALOG]
        )
    }
    settings_payload = [
        _serialize_entry(
            entry,
            current_value=db_values.get(entry["key"], entry["default"]),
            is_admin_edited=entry["key"] in db_values,
        )
        for entry in CATALOG
    ]
    groups_payload = [
        {"key": key, "label": label} for key, label in GROUPS_ORDER
    ]
    return Response({"groups": groups_payload, "settings": settings_payload})


@extend_schema(
    tags=["audit"],
    summary="Éditer un AppSetting (admin)",
    description=(
        "PATCH staff : met à jour la valeur d'un AppSetting tunable. "
        "La clé doit appartenir au catalogue (sinon 404). La valeur est "
        "validée selon le type déclaré (int/decimal/bool/enum/csv/str). "
        "Tracé en audit (``config.app_setting_updated``)."
    ),
    responses={200: OpenApiResponse(description="Le AppSetting mis à jour.")},
)
@api_view(["PATCH"])
@permission_classes([IsStaff])
def admin_settings_update(request, key: str):
    if not is_known_key(key):
        return Response(
            {"detail": f"Clé inconnue ou non tunable : {key}"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if "value" not in request.data:
        return Response(
            {"detail": "Champ 'value' requis."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    entry = get_entry(key)
    raw_value = request.data["value"]
    # Normalize bool → string
    if entry["type"] == "bool" and isinstance(raw_value, bool):
        new_value = "true" if raw_value else "false"
    else:
        new_value = str(raw_value).strip()

    ok, msg = validate_value(entry, new_value)
    if not ok:
        return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

    setting, created = AppSetting.objects.update_or_create(
        cle=key,
        defaults={
            "valeur": new_value,
            "description": entry["description"],
        },
    )

    record_audit(
        action="config.app_setting_updated",
        entite_type="AppSetting",
        entite_id=setting.pk,
        user=request.user,
        details={
            "key": key,
            "value": new_value,
            "default": entry["default"],
            "created": created,
        },
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(
        _serialize_entry(entry, current_value=new_value, is_admin_edited=True)
    )
