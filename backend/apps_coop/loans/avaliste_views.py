"""Member-facing endpoints pour les mandats d'avaliste (refonte 2026 — LOT 18).

Le membre déjà connecté au portail peut :
  - GET  /loans/me/avaliste-mandats/                 — liste de mes mandats (en attente + historique)
  - GET  /loans/me/avaliste-mandats/<id>/            — détail enrichi
  - POST /loans/me/avaliste-mandats/<id>/respond/    — accepter ou refuser (idempotent + non-rétractable Q13)

Q13 BUSINESS_RULES_2026 : une acceptation est définitive. Un consent
``ACCEPTED`` ne peut pas être rétracté en REFUSED → 400 explicite.
"""
from __future__ import annotations

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.permissions import IsMember

from .avaliste_services import respond_to_avaliste_consent
from .models import AvalisteConsent


class AvalisteRespondSerializer(serializers.Serializer):
    """Body de ``POST /loans/me/avaliste-mandats/<id>/respond/``."""

    accept = serializers.BooleanField()
    motif = serializers.CharField(
        max_length=2000,
        required=False,
        allow_blank=True,
        help_text="Optionnel mais recommandé en cas de refus.",
    )


def _row(c: AvalisteConsent) -> dict:
    lr = c.loan_request
    member = lr.member
    return {
        "id": c.id,
        "statut": c.statut,
        "statut_display": c.get_statut_display(),
        "responded_at": c.responded_at.isoformat() if c.responded_at else None,
        "refus_motif": c.refus_motif or "",
        "created_at": c.created_at.isoformat(),
        # Detail demandeur — l'avaliste a besoin de voir qui demande.
        "demandeur": {
            "id": member.id,
            "numero_membre": member.numero_membre,
            "prenom": member.prenom,
            "nom": member.nom,
        },
        "loan_request": {
            "id": lr.id,
            "montant_demande": str(lr.montant_demande),
            "duree_mois": lr.duree_mois,
            "motif": lr.motif,
            "statut": lr.statut,
            "date_soumission": lr.date_soumission.isoformat(),
        },
        # Garanties (snapshot au moment de la demande).
        "couverture": {
            "epargne_borrower": str(c.epargne_borrower_at_request),
            "epargne_avaliste": str(c.epargne_avaliste_at_request),
            "ratio": str(c.couverture_ratio),
        },
        # Réforme garantie 2026 : montant réellement gelé sur l'épargne de
        # l'avaliste (= le manque). Bloqué au retrait jusqu'à la clôture du
        # crédit. 0 tant que le mandat n'est pas ACCEPTED.
        "montant_gele": str(c.montant_caution),
        # L5 — Identité fournie par l'avaliste à l'acceptation (matérialise
        # l'acte signé). n° CNI du DEMANDEUR sur la demande liée.
        "cni_demandeur": lr.cni_demandeur or "",
        "cni_avaliste": c.cni_avaliste or "",
        "cni_avaliste_fichier": (
            c.cni_avaliste_fichier.url if c.cni_avaliste_fichier else None
        ),
    }


@extend_schema(
    tags=["loans"],
    summary="Mes mandats d'avaliste (où je suis désigné comme garant)",
    description=(
        "Renvoie la liste des `AvalisteConsent` pour lesquels le membre "
        "connecté est l'avaliste désigné. Filtre `?statut=pending|accepted|refused` "
        "optionnel. Par défaut, retourne tous les statuts (ordre antéchronologique)."
    ),
    responses={200: OpenApiResponse(description="`{ count, pending, results: Mandat[] }`")},
)
@api_view(["GET"])
@permission_classes([IsMember])
def avaliste_mandats_list(request):
    member = request.user.member
    qs = (
        AvalisteConsent.objects.filter(avaliste=member)
        .select_related("loan_request", "loan_request__member")
        .order_by("-created_at")
    )

    statut = (request.query_params.get("statut") or "").strip()
    if statut:
        qs = qs.filter(statut=statut)

    pending_count = AvalisteConsent.objects.filter(
        avaliste=member, statut=AvalisteConsent.Statut.PENDING
    ).count()

    rows = [_row(c) for c in qs[:100]]
    return Response(
        {"count": len(rows), "pending": pending_count, "results": rows}
    )


@extend_schema(
    tags=["loans"],
    summary="Détail d'un mandat d'avaliste",
    responses={
        200: OpenApiResponse(description="Détail"),
        404: OpenApiResponse(description="Mandat introuvable"),
    },
)
@api_view(["GET"])
@permission_classes([IsMember])
def avaliste_mandat_detail(request, pk: int):
    member = request.user.member
    try:
        c = (
            AvalisteConsent.objects.select_related(
                "loan_request", "loan_request__member"
            ).get(pk=pk, avaliste=member)
        )
    except AvalisteConsent.DoesNotExist:
        return Response({"detail": "Mandat introuvable."}, status=status.HTTP_404_NOT_FOUND)
    return Response(_row(c))


@extend_schema(
    tags=["loans"],
    summary="Accepter ou refuser un mandat d'avaliste",
    description=(
        "Idempotent. Une acceptation est **non-rétractable** (Q13 BUSINESS_RULES_2026) "
        "— tenter de refuser un mandat déjà accepté renvoie 400. Un refus suivant "
        "un autre refus est un no-op."
    ),
    request=AvalisteRespondSerializer,
    responses={
        200: OpenApiResponse(description="Réponse enregistrée"),
        400: OpenApiResponse(description="Rétractation interdite (Q13) / statut terminal"),
        404: OpenApiResponse(description="Mandat introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsMember])
@transaction.atomic
def avaliste_mandat_respond(request, pk: int):
    member = request.user.member
    try:
        c = (
            AvalisteConsent.objects.select_for_update()
            .select_related("loan_request", "avaliste")
            .get(pk=pk, avaliste=member)
        )
    except AvalisteConsent.DoesNotExist:
        return Response({"detail": "Mandat introuvable."}, status=status.HTTP_404_NOT_FOUND)

    s = AvalisteRespondSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    # L5 — À l'acceptation, l'avaliste fournit SON identité (n° CNI + scan).
    # C'est ce qui matérialise l'acte de prêt signé (consentement + CNI des
    # deux parties). Exigé uniquement sur accept ; un refus n'en a pas besoin.
    cni_numero = (str(request.data.get("cni_avaliste", "")) or "").strip()
    cni_fichier = request.FILES.get("cni_avaliste_fichier")
    if data["accept"]:
        if not cni_numero:
            return Response(
                {"detail": "Votre numéro de CNI est requis pour accepter le mandat."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cni_fichier is None:
            return Response(
                {"detail": "Le scan/photo de votre CNI est requis pour accepter le mandat."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        c = respond_to_avaliste_consent(
            c, accept=data["accept"], motif=data.get("motif", "")
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # Persiste l'identité de l'avaliste après une acceptation validée.
    if data["accept"]:
        c.cni_avaliste = cni_numero
        c.cni_avaliste_fichier = cni_fichier
        c.save(update_fields=["cni_avaliste", "cni_avaliste_fichier", "updated_at"])

    c.refresh_from_db()
    return Response(_row(c))
