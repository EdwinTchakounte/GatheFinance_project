"""Member-facing endpoints pour la convention prêteur (refonte 2026 — LOT 19).

Endpoints exposés (montés dans ``apps_coop/savings/urls.py``) :

  GET    /savings/me/lender/                       — état complet (consent + tranches + funding pending)
  POST   /savings/me/lender/opt-in/                — signature convention (mode A/B)
  POST   /savings/me/lender/revoke/                — révoque convention (si aucune tranche engagée)
  POST   /savings/me/lender/tranches/              — créer une tranche DISPONIBLE
  POST   /savings/me/lender/tranches/<id>/cancel/  — annuler une tranche DISPONIBLE
  POST   /savings/me/lender/funding-requests/<id>/respond/  — accepter/refuser une notif funding 24h

Les services métier vivent dans ``lender_services.py`` (consent / tranche)
et ``apps_coop/loans/funding_services.py`` (respond_to_consent_request).
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.permissions import IsMember

from apps_coop.loans.funding_services import respond_to_consent_request
from apps_coop.loans.models import LenderConsentRequest

from .lender_services import (
    add_tranche,
    opt_in_lender,
    revoke_consent,
)
from .models import LenderConsent, LenderTranche


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


class LenderOptInSerializer(serializers.Serializer):
    is_global = serializers.BooleanField(
        default=False,
        help_text="True = Mode A (solde entier prêtable). False = Mode B (tranches).",
    )


class LenderAddTrancheSerializer(serializers.Serializer):
    montant = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("100")
    )


class FundingResponseSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    motif = serializers.CharField(
        max_length=2000, required=False, allow_blank=True
    )

    def validate(self, attrs):
        if not attrs["accept"] and not (attrs.get("motif") or "").strip():
            raise serializers.ValidationError(
                {"motif": "Motif requis en cas de refus."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Sérialisation read-side
# ---------------------------------------------------------------------------


def _tranche_row(t: LenderTranche) -> dict:
    return {
        "id": t.id,
        "montant": str(t.montant),
        "statut": t.statut,
        "statut_display": t.get_statut_display(),
        "engaged_in_loan_id": t.engaged_in_loan_id,
        "engaged_at": t.engaged_at.isoformat() if t.engaged_at else None,
        "released_at": t.released_at.isoformat() if t.released_at else None,
        "created_at": t.created_at.isoformat(),
    }


def _consent_row(c: LenderConsent | None) -> dict | None:
    if c is None:
        return None
    return {
        "id": c.id,
        "is_global": c.is_global,
        "is_active": c.is_active,
        "convention_signed_at": c.convention_signed_at.isoformat(),
        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
    }


def _funding_pending_row(cr: LenderConsentRequest) -> dict:
    fr = cr.funding_request
    loan = fr.loan
    member = loan.member
    return {
        "id": cr.id,
        "statut": cr.statut,
        "montant_propose": str(cr.montant_propose),
        "deadline": cr.deadline.isoformat(),
        "funding_request_id": fr.id,
        "wave_number": fr.wave_number,
        "loan": {
            "id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "montant_total": str(fr.montant_total),
            "duree_mois": loan.duree_mois,
        },
        "borrower": {
            "id": member.id,
            "numero_membre": member.numero_membre,
            "prenom": member.prenom,
            "nom": member.nom,
        },
    }


def _aggregate_state(member) -> dict:
    consent = LenderConsent.objects.filter(member=member).first()
    tranches = LenderTranche.objects.filter(member=member).order_by("-created_at")
    by_statut = {
        "disponible": Decimal("0"),
        "engagee": Decimal("0"),
        "liberee": Decimal("0"),
        "annulee": Decimal("0"),
    }
    for t in tranches:
        if t.statut in by_statut:
            by_statut[t.statut] += Decimal(t.montant)

    pending_consents = (
        LenderConsentRequest.objects.filter(
            lender=member, statut=LenderConsentRequest.Statut.PENDING
        )
        .select_related("funding_request", "funding_request__loan", "funding_request__loan__member")
        .order_by("deadline")
    )

    return {
        "consent": _consent_row(consent),
        "tranches": [_tranche_row(t) for t in tranches],
        "totals": {k: str(v) for k, v in by_statut.items()},
        "pending_funding_requests": [_funding_pending_row(cr) for cr in pending_consents],
        "pending_count": pending_consents.count(),
    }


# ---------------------------------------------------------------------------
# GET /savings/me/lender/ — vue d'ensemble
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["savings"],
    summary="Mon espace prêteur (convention + tranches + notifications funding)",
    responses={200: OpenApiResponse(description="État agrégé du membre côté prêteur")},
)
@api_view(["GET"])
@permission_classes([IsMember])
def lender_me(request):
    return Response(_aggregate_state(request.user.member))


# ---------------------------------------------------------------------------
# POST /savings/me/lender/opt-in/ — signer la convention
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["savings"],
    summary="Signer la convention prêteur (mode A global ou B tranches)",
    request=LenderOptInSerializer,
    responses={
        201: OpenApiResponse(description="Convention signée"),
        200: OpenApiResponse(description="Convention déjà active (idempotent)"),
        400: OpenApiResponse(description="Ancienneté insuffisante"),
    },
)
@api_view(["POST"])
@permission_classes([IsMember])
@transaction.atomic
def lender_opt_in(request):
    member = request.user.member
    s = LenderOptInSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    existed = LenderConsent.objects.filter(member=member, revoked_at__isnull=True).exists()
    try:
        consent = opt_in_lender(
            member=member,
            is_global=s.validated_data["is_global"],
            actor=request.user,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        _aggregate_state(member),
        status=status.HTTP_200_OK if existed else status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# POST /savings/me/lender/revoke/ — révoquer la convention
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["savings"],
    summary="Révoquer ma convention prêteur (impossible si une tranche est engagée)",
    responses={
        200: OpenApiResponse(description="Convention révoquée"),
        400: OpenApiResponse(description="Tranches encore engagées"),
        404: OpenApiResponse(description="Aucune convention active"),
    },
)
@api_view(["POST"])
@permission_classes([IsMember])
@transaction.atomic
def lender_revoke(request):
    member = request.user.member
    if not LenderConsent.objects.filter(member=member, revoked_at__isnull=True).exists():
        return Response(
            {"detail": "Aucune convention active."}, status=status.HTTP_404_NOT_FOUND
        )
    try:
        revoke_consent(member=member, actor=request.user)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_aggregate_state(member))


# ---------------------------------------------------------------------------
# POST /savings/me/lender/tranches/ — créer une tranche
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["savings"],
    summary="Créer une tranche d'épargne prêtable (DISPONIBLE)",
    request=LenderAddTrancheSerializer,
    responses={
        201: OpenApiResponse(description="Tranche créée"),
        400: OpenApiResponse(description="Montant invalide / pas prêteur"),
    },
)
@api_view(["POST"])
@permission_classes([IsMember])
@transaction.atomic
def lender_add_tranche(request):
    member = request.user.member
    s = LenderAddTrancheSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    try:
        t = add_tranche(
            member=member,
            montant=s.validated_data["montant"],
            actor=request.user,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_tranche_row(t), status=status.HTTP_201_CREATED)


# Récupération d'une tranche = ADMIN uniquement (funding/lender-admin). Le
# membre place son argent délibérément et n'annule pas lui-même ses tranches —
# il est seulement notifié. Pas de vue membre de cancel.


# ---------------------------------------------------------------------------
# POST /savings/me/lender/funding-requests/<id>/respond/ — accepter/refuser
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["savings"],
    summary="Accepter ou refuser une notification de funding crédit (24h)",
    description=(
        "L'`id` est celui de la `LenderConsentRequest` envoyée par le système "
        "lors d'une vague de funding. Idempotent : si déjà répondu, no-op. "
        "Refus → motif obligatoire."
    ),
    request=FundingResponseSerializer,
    responses={
        200: OpenApiResponse(description="Réponse enregistrée"),
        400: OpenApiResponse(description="Motif manquant / statut invalide"),
        404: OpenApiResponse(description="Notification introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsMember])
@transaction.atomic
def lender_funding_respond(request, pk: int):
    member = request.user.member
    try:
        cr = LenderConsentRequest.objects.select_for_update().get(
            pk=pk, lender=member
        )
    except LenderConsentRequest.DoesNotExist:
        return Response(
            {"detail": "Notification introuvable."}, status=status.HTTP_404_NOT_FOUND
        )
    s = FundingResponseSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    try:
        cr = respond_to_consent_request(
            consent_request=cr,
            accept=s.validated_data["accept"],
            motif=s.validated_data.get("motif", ""),
            actor=request.user,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    cr.refresh_from_db()
    return Response(
        {
            "id": cr.id,
            "statut": cr.statut,
            "responded_at": cr.responded_at.isoformat() if cr.responded_at else None,
            "refus_motif": cr.refus_motif or "",
            "message": (
                "Acceptation enregistrée." if s.validated_data["accept"] else "Refus enregistré."
            ),
        }
    )
