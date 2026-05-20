"""Members API — placeholder viewsets (filled UC by UC).

For now we only expose the "me" resource so the portal can show the member's
profile. Admin-facing list/detail endpoints come next.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import client_ip, record as record_audit

from . import services
from .models import Member, MembershipRequest
from .permissions import IsAdmin, IsMember, IsStaff
from .serializers import (
    MemberReadSerializer,
    MembershipApproveSerializer,
    MembershipRejectSerializer,
    MembershipRequestReadSerializer,
)


@extend_schema(
    tags=["members"],
    summary="Profil du membre connecté",
    description=(
        "Renvoie les infos de profil du `Member` lié à l'`User` connecté : numéro "
        "membre, nom/prénom, téléphone, statut, date d'adhésion."
    ),
)
class MemberMeView(generics.RetrieveAPIView):
    """GET / PATCH /api/v1/members/me/ — profil du membre connecté.

    PATCH : édition des champs libres (prenom, nom, phone, adresse, profession).
    Le numero_membre, le statut et la date d'adhésion ne sont PAS éditables par
    le membre (gérés par l'administration).
    """

    permission_classes = [IsMember]

    _EDITABLE = ("prenom", "nom", "phone", "adresse", "profession")

    def _payload(self, m) -> dict:
        return {
            "id": m.id,
            "numero_membre": m.numero_membre,
            "nom": m.nom,
            "prenom": m.prenom,
            "phone": m.phone,
            "adresse": m.adresse,
            "profession": m.profession,
            "statut": m.statut,
            "date_adhesion": m.date_adhesion.isoformat(),
        }

    def retrieve(self, request, *args, **kwargs):
        return Response(self._payload(request.user.member))

    def patch(self, request, *args, **kwargs):
        m = request.user.member
        changed = []
        for field in self._EDITABLE:
            if field in request.data:
                value = (request.data.get(field) or "").strip()
                if getattr(m, field) != value:
                    setattr(m, field, value)
                    changed.append(field)
        if changed:
            m.save(update_fields=[*changed, "updated_at"])
            record_audit(
                action="member.profile_updated",
                entite_type="Member",
                entite_id=m.id,
                user=request.user,
                details={"fields": changed},
                ip=client_ip(request),
            )
        return Response(self._payload(m))


@extend_schema(
    tags=["booklet"],
    summary="Mes commandes de carnet de collecte",
    description=(
        "Liste les `BookletOrder` du membre connecté (Article 4 — carnet de "
        "collecte 1 000 FCFA). Une commande est créée automatiquement quand un "
        "paiement `frais_carnet` est validé. Statuts : payee → en_impression → "
        "delivree."
    ),
)
@api_view(["GET"])
@permission_classes([IsMember])
def booklet_orders_me(request):
    from .models import BookletOrder
    from .serializers import BookletOrderReadSerializer

    qs = BookletOrder.objects.filter(member=request.user.member).order_by("-created_at")
    return Response({"results": BookletOrderReadSerializer(qs, many=True).data})


# ---------------------------------------------------------------------------
# Admin endpoints — used by the Next.js admin dashboard
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — liste des demandes d'adhésion",
    description=(
        "Liste des `MembershipRequest`. Accepte `?statut=en_attente|approuvee|rejetee` "
        "pour filtrer. Permission : `IsStaff`."
    ),
    responses={200: MembershipRequestReadSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_membership_requests(request):
    qs = MembershipRequest.objects.order_by("-created_at")
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    return Response(MembershipRequestReadSerializer(qs, many=True).data)


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — enregistrer l'entretien d'admission (Article 3)",
    description=(
        "Consigne l'entretien obligatoire avec le comité : date, avis et issue "
        "(favorable ou non). L'approbation d'une demande est bloquée tant que "
        "l'entretien n'est pas enregistré. Permission : `IsStaff`."
    ),
    responses={
        200: MembershipRequestReadSerializer,
        404: OpenApiResponse(description="Demande introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_record_interview(request, pk: int):
    from django.utils import timezone

    try:
        req = MembershipRequest.objects.get(pk=pk)
    except MembershipRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    avis = (request.data.get("avis") or "").strip()
    favorable = request.data.get("favorable")
    # Date fournie ou maintenant par défaut.
    req.date_entretien = timezone.now()
    req.entretien_avis = avis
    if isinstance(favorable, bool):
        req.entretien_favorable = favorable
    req.save(update_fields=["date_entretien", "entretien_avis", "entretien_favorable", "updated_at"])

    record_audit(
        action="membership.interview_recorded",
        entite_type="MembershipRequest",
        entite_id=req.id,
        user=request.user,
        details={"favorable": req.entretien_favorable, "avis_len": len(avis)},
        ip=client_ip(request),
    )
    return Response(MembershipRequestReadSerializer(req).data)


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — approuver une demande d'adhésion",
    description=(
        "Crée atomiquement User + Member + SavingsAccount. Permission : `IsAdmin`. "
        "Idempotent : si la demande est déjà approuvée, renvoie le Member existant."
    ),
    request=MembershipApproveSerializer,
    responses={
        200: MembershipRequestReadSerializer,
        400: OpenApiResponse(description="Statut incompatible"),
        404: OpenApiResponse(description="Demande introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_approve_membership_request(request, pk: int):
    try:
        req = MembershipRequest.objects.get(pk=pk)
    except MembershipRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)
    serializer = MembershipApproveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        services.approve_membership_request(
            req,
            instructed_by=request.user,
            prenom=serializer.validated_data.get("prenom"),
            nom=serializer.validated_data.get("nom"),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    req.refresh_from_db()
    return Response(MembershipRequestReadSerializer(req).data)


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — rejeter une demande d'adhésion",
    description="Pose `statut=rejetee` + `motif_rejet`. Permission : `IsAdmin`.",
    request=MembershipRejectSerializer,
    responses={
        200: MembershipRequestReadSerializer,
        400: OpenApiResponse(description="Statut incompatible ou motif vide"),
        404: OpenApiResponse(description="Demande introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_reject_membership_request(request, pk: int):
    try:
        req = MembershipRequest.objects.get(pk=pk)
    except MembershipRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)
    serializer = MembershipRejectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        services.reject_membership_request(
            req,
            instructed_by=request.user,
            motif=serializer.validated_data["motif"],
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    req.refresh_from_db()
    return Response(MembershipRequestReadSerializer(req).data)


_ADMIN_MEMBERS_PAGE_SIZE = 200


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — liste des membres",
    description=(
        "Annuaire des `Member`. Filtres : `?statut=actif|suspendu|radie`, "
        "`?q=<nom|prenom|numero|email>`. Permission : `IsStaff`."
    ),
    responses={200: OpenApiResponse(description="`{ count, results: Member[] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_members(request):
    qs = Member.objects.select_related("user").order_by("-date_adhesion")
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    q = (request.query_params.get("q") or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(numero_membre__icontains=q)
            | Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(phone__icontains=q)
            | Q(user__email__icontains=q)
        )
    count = qs.count()
    rows = qs[:_ADMIN_MEMBERS_PAGE_SIZE]
    return Response(
        {
            "count": count,
            "results": MemberReadSerializer(rows, many=True).data,
        }
    )


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — KPIs synthétiques",
    description=(
        "Compteurs principaux pour le dashboard staff : membres par statut, "
        "files d'attente, encours crédit total, solde total épargne, derniers paiements."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_dashboard_kpis(request):
    from django.db.models import Sum

    from apps_coop.loans.models import Loan, LoanRequest
    from apps_coop.payments.models import Payment
    from apps_coop.payments.serializers import PaymentReadSerializer
    from apps_coop.savings.models import SavingsAccount

    members_active = Member.objects.filter(statut=Member.Statut.ACTIF).count()
    members_suspended = Member.objects.filter(statut=Member.Statut.SUSPENDU).count()
    pending_adhesions = MembershipRequest.objects.filter(
        statut=MembershipRequest.Statut.EN_ATTENTE
    ).count()
    loans_pending = LoanRequest.objects.filter(
        statut=LoanRequest.Statut.EN_INSTRUCTION
    ).count()
    encours = (
        Loan.objects.filter(statut__in=[Loan.Statut.ACTIF, Loan.Statut.EN_RETARD])
        .aggregate(total=Sum("solde_restant"))["total"]
        or 0
    )
    epargne_total = (
        SavingsAccount.objects.aggregate(total=Sum("solde"))["total"] or 0
    )
    payments_recent = Payment.objects.filter(
        statut=Payment.Statut.VALIDE
    ).order_by("-date_validation")[:5]

    return Response(
        {
            "members": {"actif": members_active, "suspendu": members_suspended},
            "queues": {
                "adhesions_en_attente": pending_adhesions,
                "credits_en_instruction": loans_pending,
            },
            "finance": {
                "encours_credit": str(encours),
                "epargne_total": str(epargne_total),
            },
            "recent_payments": PaymentReadSerializer(payments_recent, many=True).data,
        }
    )
