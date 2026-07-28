"""Endpoint public exposant les campagnes micro-crédit actives (LOT 11).

Utilisé par le portail mobile + la vitrine pour afficher les flyers de
campagnes ouvertes — un membre peut découvrir une campagne ciblée vers
quelqu'un qu'il connaît et partager le flyer. Distinct des endpoints
admin qui pilotent la création/modification.
"""

import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import MicrocreditCampaign


logger = logging.getLogger(__name__)


def _flyer_url(c: MicrocreditCampaign, request) -> str:
    """Toujours retourner une URL ABSOLUE et PUBLIQUE : flyer uploadé si présent,
    sinon photo stock Unsplash CDN d'après le profil ciblé. Source unique de
    vérité — mobile / portail / vitrine / admin consomment cette URL directement.

    ⚠️ La vitrine (Next.js) fetche côté serveur via l'hôte INTERNE Docker
    (``backend:8000``), injoignable depuis le navigateur. On NE construit donc
    jamais l'URL du flyer à partir de l'hôte de la requête : on préfère une base
    publique (``MEDIA_DOMAIN`` → ``flyer.url`` déjà absolue ; sinon
    ``PUBLIC_BASE_URL``, le domaine public du backend). Repli sur l'hôte de la
    requête seulement si aucune base publique n'est configurée (dev).
    """
    try:
        relative = c.flyer.url if c.flyer else None
    except (ValueError, AttributeError):
        relative = None
    if relative:
        # Déjà absolue (MEDIA_DOMAIN posé) → telle quelle.
        if relative.startswith(("http://", "https://")):
            return relative
        from django.conf import settings

        base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
        if base:
            return base + relative
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
        "membre_requis": c.membre_requis,
        # Frais d'étude : None = tarif standard, "0.00" = gratuit (« sans frais »).
        "frais_etude_montant": (
            str(c.frais_etude_montant) if c.frais_etude_montant is not None else None
        ),
        "documents_requis": list(c.documents_requis or []),
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
            "membre_requis",
            "frais_etude_montant",
            "documents_requis",
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


@extend_schema(
    tags=["loans"],
    summary="Détail public d'une campagne (deep-link partage)",
    description=(
        "Renvoie une campagne par id, même clôturée (pour ne pas casser un lien "
        "partagé). Le champ `is_open` indique si les candidatures sont encore "
        "ouvertes aujourd'hui."
    ),
    responses={200: OpenApiResponse(description="Campaign + is_open")},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def public_campaign_detail(request, pk):
    from django.shortcuts import get_object_or_404

    today = timezone.localdate()
    c = get_object_or_404(
        MicrocreditCampaign.objects.filter(deleted_at__isnull=True), pk=pk
    )
    data = _row(c, request)
    data["is_open"] = bool(
        c.actif and c.date_debut <= today <= c.date_fin
    )
    return Response(data)


@extend_schema(
    tags=["loans"],
    summary="Candidature publique à une campagne (visiteur non-membre)",
    description=(
        "POST public (AllowAny). Enregistre une candidature pour une campagne "
        "``membre_requis=False``. Le compte n'est PAS créé ici — l'admin décide, "
        "et à l'acceptation un compte est créé sans frais d'adhésion. "
        "Body : nom, prenom, phone, email (requis), montant, motif."
    ),
)
@api_view(["POST"])
@permission_classes([AllowAny])
def public_campaign_apply(request, pk):
    from decimal import Decimal, InvalidOperation

    from .microcampaign_services import create_public_application

    try:
        campaign = MicrocreditCampaign.objects.get(pk=pk, deleted_at__isnull=True)
    except MicrocreditCampaign.DoesNotExist:
        return Response({"detail": "Campagne introuvable."}, status=404)

    data = request.data
    missing = [
        f for f in ("nom", "prenom", "email", "montant")
        if not str(data.get(f, "")).strip()
    ]
    if missing:
        return Response(
            {"detail": f"Champs requis manquants : {', '.join(missing)}."},
            status=400,
        )
    try:
        montant = Decimal(str(data.get("montant")))
    except (InvalidOperation, TypeError, ValueError):
        return Response({"detail": "Montant invalide."}, status=400)

    # Pièces justificatives : un fichier par libellé de ``documents_requis``,
    # envoyé en multipart sous la clé ``doc_<index>`` (ordre de la liste).
    requis = [str(d).strip() for d in (campaign.documents_requis or []) if str(d).strip()]
    documents = [
        (label, request.FILES.get(f"doc_{i}"))
        for i, label in enumerate(requis)
    ]

    try:
        app = create_public_application(
            campaign,
            nom=str(data.get("nom")),
            prenom=str(data.get("prenom")),
            phone=str(data.get("phone", "")),
            email=str(data.get("email")),
            montant=montant,
            motif=str(data.get("motif", "")),
            documents=documents,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    except Exception:  # noqa: BLE001 — jamais de 500 pour un candidat public
        logger.exception("public_campaign_apply a échoué (campagne #%s)", pk)
        return Response(
            {
                "detail": (
                    "Une erreur est survenue à l'enregistrement de votre "
                    "candidature. Réessayez, ou contactez la coopérative si le "
                    "problème persiste."
                )
            },
            status=400,
        )

    return Response(
        {
            "id": app.id,
            "statut": app.statut,
            "message": (
                "Candidature enregistrée. La coopérative l'étudie et te "
                "recontactera par email si elle est acceptée."
            ),
        },
        status=201,
    )
