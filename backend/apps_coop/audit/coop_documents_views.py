"""Endpoints publics autour de CooperativeAsset.

GET /api/v1/coop-documents/ — membre ou portail public.
Renvoie les URLs des PDFs téléchargeables (règlement intérieur + spécimen
de carnet) si l'admin les a uploadés. Sinon null, et le front affiche
"Bientôt disponible".
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import CooperativeAsset


def _file_url(request, file_field) -> str | None:
    """Renvoie l'URL absolue d'un FileField (ou ``None`` si vide)."""
    if not file_field:
        return None
    try:
        return request.build_absolute_uri(file_field.url)
    except Exception:  # noqa: BLE001 — defensive (storage absent en dev)
        return None


@extend_schema(
    tags=["coop"],
    summary="Documents officiels de la cooperative",
    description=(
        "Retourne les URLs des PDFs telechargeables par le membre depuis "
        "l'application mobile / le portail : reglement interieur + specimen "
        "de carnet. Chaque champ est null si l'admin n'a pas encore uploade "
        "le PDF correspondant."
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def coop_documents(request):
    asset = CooperativeAsset.get_solo()
    return Response(
        {
            "reglement_interieur": {
                "url": _file_url(request, asset.reglement_interieur),
                "uploaded_at": asset.reglement_uploaded_at,
                "label": "Reglement interieur",
            },
            "carnet_specimen": {
                "url": _file_url(request, asset.carnet_specimen),
                "uploaded_at": asset.carnet_specimen_uploaded_at,
                "label": "Specimen carnet",
            },
        }
    )
