"""Onglet « Notifications » de l'admin — échéances des processus métier.

Endpoint de LECTURE : il n'agit sur rien, il rend visible ce qui arrive à
terme (clôture mensuelle des collectes, crédits au-delà de leur date butoire,
campagnes échues, cycles de collecte à clôturer, maturités d'épargne,
réinscriptions dues). L'exécution reste le travail des crons.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.permissions import ResourceAccess

from .deadlines import DEFAULT_HORIZON_DAYS, collect_deadlines, deadlines_summary


@extend_schema(
    tags=["admin"],
    summary="🔒 Admin — échéances des processus (onglet Notifications)",
    description=(
        "Rassemble les délais de fin de chaque processus : clôture mensuelle "
        "des collectes, crédits au-delà de leur date butoire ou en approche, "
        "campagnes micro-crédit échues ou bientôt terminées, cycles de "
        "collecte particulière à clôturer, épargnes classiques à maturité, "
        "réinscriptions annuelles dues.\n\n"
        "Chaque entrée porte sa gravité : `urgent` (dépassé), `proche` "
        "(≤ 7 jours), `info`. Les entrées à volume nul restent affichées — "
        "savoir qu'il n'y a rien à traiter est une information.\n\n"
        "Lecture seule : aucun envoi, aucune modification. Permission : "
        "ressource `notifications`."
    ),
    parameters=[
        OpenApiParameter(
            name="horizon",
            type=int,
            description=(
                f"Fenêtre d'anticipation en jours (défaut {DEFAULT_HORIZON_DAYS}, "
                "borné à 1–365)."
            ),
        ),
    ],
    responses={200: OpenApiResponse(description="Échéances + compteurs d'en-tête")},
)
@api_view(["GET"])
@permission_classes([ResourceAccess("notifications")])
def admin_deadlines(request):
    try:
        horizon = int(request.GET.get("horizon") or DEFAULT_HORIZON_DAYS)
    except (TypeError, ValueError):
        horizon = DEFAULT_HORIZON_DAYS
    # Borne défensive : un horizon absurde ferait balayer toute la base.
    horizon = max(1, min(horizon, 365))

    cartes = collect_deadlines(horizon_days=horizon)
    return Response(
        {
            "horizon_days": horizon,
            "summary": deadlines_summary(cartes),
            "results": cartes,
        }
    )
