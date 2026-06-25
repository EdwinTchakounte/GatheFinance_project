"""Endpoint public exposant les campagnes micro-crédit actives (LOT 11).

Utilisé par le portail mobile + la vitrine pour afficher les flyers de
campagnes ouvertes — un membre peut découvrir une campagne ciblée vers
quelqu'un qu'il connaît et partager le flyer. Distinct des endpoints
admin qui pilotent la création/modification.
"""

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import MicrocreditCampaign


def _flyer_url(c: MicrocreditCampaign, request) -> str:
    """Toujours retourner une URL : flyer uploadé si présent, sinon photo
    stock Unsplash CDN choisie d'après le profil ciblé. Source unique de
    vérité — le mobile / portail / admin consomment cette URL directement.
    """
    try:
        relative = c.flyer.url if c.flyer else None
    except (ValueError, AttributeError):
        relative = None
    if relative:
        return request.build_absolute_uri(relative)
    from apps_cms.cms.stock_images import campaign_image_for
    return campaign_image_for(c.nom, c.profil_cible)


def _row(c: MicrocreditCampaign, request) -> dict:
    return {
        "id": c.id,
        "nom": c.nom,
        "profil_cible": c.profil_cible,
        "date_debut": c.date_debut.isoformat(),
        "date_fin": c.date_fin.isoformat(),
        "montant_min": str(c.montant_min),
        "montant_max": str(c.montant_max),
        "taux_interet": str(c.taux_interet),
        "nb_jours_recouvrement": c.nb_jours_recouvrement,
        "flyer_url": _flyer_url(c, request),
    }


@extend_schema(
    tags=["loans"],
    summary="Liste publique des campagnes micro-crédit ouvertes",
    description=(
        "Renvoie les campagnes pour lesquelles ``actif=True`` ET la date "
        "du jour est comprise dans la fenêtre ``[date_debut, date_fin]``. "
        "Accessible sans authentification — utilisé par le mobile (carousel "
        "Home) et la vitrine pour la communication des flyers."
    ),
    responses={200: OpenApiResponse(description="`{ results: Campaign[] }`")},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def public_active_campaigns(request):
    """Pagination simple `?limit=N&offset=M`.

    Renvoie ``{count, next, previous, results}`` à l'image de DRF, pour
    que le mobile puisse charger les pages suivantes au scroll. `limit`
    par défaut 10, plafonné à 50 pour éviter qu'un client demande tout
    en une fois.
    """
    today = timezone.localdate()
    qs = (
        MicrocreditCampaign.objects.filter(
            actif=True,
            date_debut__lte=today,
            date_fin__gte=today,
        )
        .order_by("date_fin", "-id")
        .only(
            "id",
            "nom",
            "profil_cible",
            "date_debut",
            "date_fin",
            "montant_min",
            "montant_max",
            "taux_interet",
            "nb_jours_recouvrement",
            "flyer",
        )
    )

    try:
        limit = int(request.GET.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    try:
        offset = int(request.GET.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    total = qs.count()
    items = qs[offset : offset + limit]
    base = request.build_absolute_uri(request.path)

    def _link(off: int) -> str | None:
        if off < 0 or off >= total:
            return None
        return f"{base}?limit={limit}&offset={off}"

    return Response(
        {
            "count": total,
            "next": _link(offset + limit) if offset + limit < total else None,
            "previous": _link(offset - limit) if offset > 0 else None,
            "results": [_row(c, request) for c in items],
        }
    )
