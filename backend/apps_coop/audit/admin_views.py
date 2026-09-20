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

from .models import AppSetting, CooperativeAsset
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
def _mobile_version_tuple(value: str) -> tuple[int, ...]:
    """Version « 1.2.0 » -> (1, 2, 0). Le format est deja valide en amont."""
    return tuple(int(p) for p in value.split("."))


def _check_mobile_gate(key: str, new_value: str) -> tuple[bool, str]:
    """Refuse une porte de mise a jour impossible a franchir.

    `mobile.min_version` bloque l'application en dessous du seuil. Le poser
    au-dessus de `mobile.latest_version` enferme TOUS les membres : ecran de
    blocage, invitation a mettre a jour, et aucune version a installer. Le
    cas est irrattrapable depuis le telephone — seul un acces admin le
    corrige. On l'interdit donc a l'ecriture.
    """
    if key not in ("mobile.min_version", "mobile.latest_version"):
        return True, ""

    autre = (
        "mobile.latest_version"
        if key == "mobile.min_version"
        else "mobile.min_version"
    )
    entry_autre = get_entry(autre) or {}
    ligne = AppSetting.objects.filter(cle=autre).first()
    valeur_autre = ligne.valeur if ligne else entry_autre.get("default", "")
    if not valeur_autre:
        return True, ""

    try:
        minimale, derniere = (
            (_mobile_version_tuple(new_value), _mobile_version_tuple(valeur_autre))
            if key == "mobile.min_version"
            else (_mobile_version_tuple(valeur_autre), _mobile_version_tuple(new_value))
        )
    except ValueError:
        # Valeur historique mal formee en base : on ne bloque pas l'edition,
        # c'est justement elle qui permet de reparer.
        return True, ""

    if minimale > derniere:
        return False, (
            f"La version minimale ({'.'.join(map(str, minimale))}) depasserait "
            f"la derniere version publiee ({'.'.join(map(str, derniere))}) : "
            "les membres seraient bloques sans mise a jour disponible. "
            "Publiez d'abord la nouvelle version, puis relevez le minimum."
        )
    return True, ""


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
        if not entry.get("hidden")  # réglages obsolètes masqués de l'UI
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

    ok, msg = _check_mobile_gate(key, new_value)
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


# ---------------------------------------------------------------------------
# CooperativeAsset — règlement intérieur PDF (singleton)
# ---------------------------------------------------------------------------


def _serialize_asset(asset: CooperativeAsset) -> dict:
    f = asset.reglement_interieur
    return {
        "reglement_interieur": {
            "uploaded": bool(f),
            "url": f.url if f else None,
            "name": f.name.rsplit("/", 1)[-1] if f else None,
            "size": f.size if f else 0,
            "uploaded_at": asset.reglement_uploaded_at.isoformat()
            if asset.reglement_uploaded_at
            else None,
            "uploaded_by": (
                asset.reglement_uploaded_by.username
                if asset.reglement_uploaded_by
                else None
            ),
        }
    }


@extend_schema(
    tags=["admin"],
    summary="Asset coopérative (singleton) — règlement intérieur",
    description=(
        "GET retourne l'état du règlement intérieur (URL, taille, métadonnées). "
        "Le PDF est joint automatiquement au mail de bienvenue UC1 quand il existe."
    ),
    responses={200: OpenApiResponse(description="Asset payload")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_cooperative_asset_get(request):
    asset = CooperativeAsset.get_solo()
    return Response(_serialize_asset(asset))


@extend_schema(
    tags=["admin"],
    summary="Uploader/remplacer le règlement intérieur PDF",
    description=(
        "POST multipart : field name `file` — PDF du règlement intérieur. "
        "Limite : 10 Mo. Replacement complet (l'ancien fichier reste sur disque "
        "mais n'est plus référencé). Trace l'action dans l'audit log."
    ),
    request={"multipart/form-data": {"type": "object", "properties": {"file": {"type": "string", "format": "binary"}}}},
    responses={200: OpenApiResponse(description="OK, asset mis à jour")},
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_cooperative_asset_upload_reglement(request):
    from django.utils import timezone

    f = request.FILES.get("file")
    if f is None:
        return Response(
            {"detail": "Champ `file` requis (multipart)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    max_size = 10 * 1024 * 1024  # 10 Mo
    if f.size > max_size:
        return Response(
            {"detail": "Fichier trop volumineux (max 10 Mo)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not f.name.lower().endswith(".pdf"):
        return Response(
            {"detail": "Format PDF requis."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    asset = CooperativeAsset.get_solo()
    asset.reglement_interieur = f
    asset.reglement_uploaded_by = request.user
    asset.reglement_uploaded_at = timezone.now()
    asset.save()

    record_audit(
        action="config.reglement_uploaded",
        entite_type="CooperativeAsset",
        entite_id=asset.pk,
        user=request.user,
        details={
            "filename": f.name,
            "size": f.size,
        },
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response(_serialize_asset(asset))
