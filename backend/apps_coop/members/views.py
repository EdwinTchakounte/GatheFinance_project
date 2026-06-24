"""Members API — placeholder viewsets (filled UC by UC).

For now we only expose the "me" resource so the portal can show the member's
profile. Admin-facing list/detail endpoints come next.
"""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import client_ip, record as record_audit

from . import services
from .models import BRCDocument, Member, MembershipRequest
from .permissions import IsActiveMember, IsAdmin, IsMember, IsStaff
from .serializers import (
    BRCDocumentAdminReadSerializer,
    BRCDocumentReadSerializer,
    BRCDocumentRejectSerializer,
    BRCDocumentUploadSerializer,
    MemberReadSerializer,
    MemberReinscriptionConfirmSerializer,
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


@extend_schema(
    tags=["members"],
    summary="Recherche d'avalistes éligibles (typeahead)",
    description=(
        "Renvoie jusqu'à 10 membres ACTIFS + SENIORS qui matchent `q` "
        "(préfixe sur `numero_membre` OU sous-chaîne casefold sur `nom`). "
        "Exclut le membre courant (ne peut pas être son propre garant). "
        "Utilisé par le sheet mobile de demande de crédit (§7.2) pour "
        "remplacer la saisie texte libre du numéro/nom avaliste par un "
        "picker. La cap solde (memory note avaliste-cap-solde) sera "
        "renseignée par un autre lot — le solde brut n'est pas exposé ici."
    ),
)
@api_view(["GET"])
@permission_classes([IsActiveMember])
def search_eligible_avalistes(request):
    """Typeahead — préfix `q` ≥ 2 chars, autrement liste vide."""
    from django.db.models import Q

    me = request.user.member
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return Response({"results": []})

    base = Member.objects.exclude(pk=me.pk).filter(statut=Member.Statut.ACTIF)
    qs = base.filter(Q(numero_membre__icontains=q) | Q(nom__icontains=q))[:30]

    # `is_senior` est un computed @property en Python — on filtre côté
    # appli plutôt qu'en SQL pour rester aligné sur le seuil configurable
    # (cf. apps_coop.members.models.Member.is_senior).
    #
    # Memory note `avaliste-cap-solde` : on expose la capacité de caution
    # disponible (solde cumulé − cautions déjà engagées) pour que le mobile
    # affiche un hint sous chaque candidat et désactive ceux qui n'ont plus
    # de marge.
    from apps_coop.loans.avaliste_services import member_caution_capacity

    results = []
    for m in qs:
        if not m.is_senior:
            continue
        try:
            solde, engaged, capacity = member_caution_capacity(m)
        except Exception:  # noqa: BLE001 — best-effort, never block typeahead
            solde = engaged = capacity = 0
        results.append({
            "numero_membre": m.numero_membre,
            "nom": m.nom,
            "prenom": m.prenom,
            "is_senior": True,
            "solde_total": str(solde),
            "cautions_engagees": str(engaged),
            "capacite_caution": str(capacity),
        })
        if len(results) >= 10:
            break
    return Response({"results": results})


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
@extend_schema(
    tags=["members"],
    summary="🔒 Admin — confirmer la réinscription annuelle (A2)",
    description=(
        "Acte la re-souscription annuelle d'un `Member` : décale "
        "`date_derniere_reinscription` à aujourd'hui (la prochaine échéance "
        "passe à +12 mois). Best-effort : émet l'événement "
        "`member.reinscription_confirmed`. Idempotent le même jour. "
        "Permission : `IsAdmin`."
    ),
    request=MemberReinscriptionConfirmSerializer,
    responses={
        200: MemberReadSerializer,
        404: OpenApiResponse(description="Membre introuvable."),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_confirm_member_reinscription(request, pk: int):
    try:
        member = Member.objects.get(pk=pk)
    except Member.DoesNotExist:
        return Response({"detail": "Membre introuvable."}, status=status.HTTP_404_NOT_FOUND)

    serializer = MemberReinscriptionConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    services.confirm_member_reinscription(
        member,
        confirmed_by=request.user,
        paid_amount=serializer.validated_data.get("paid_amount"),
        note=serializer.validated_data.get("note", ""),
    )
    member.refresh_from_db()
    return Response(MemberReadSerializer(member).data)


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
        "`?q=<nom|prenom|numero|email>`, `?reinscription_overdue=true` "
        "(membres dont l'anniversaire annuel est dépassé), "
        "`?reinscription_due_soon=<jours>` (échéance dans N jours ou moins). "
        "Permission : `IsStaff`."
    ),
    responses={200: OpenApiResponse(description="`{ count, results: Member[] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_members(request):
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone

    qs = Member.objects.select_related("user").order_by("-date_adhesion")
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    q = (request.query_params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(numero_membre__icontains=q)
            | Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(phone__icontains=q)
            | Q(user__email__icontains=q)
        )

    # A2 — Filtres de réinscription annuelle.
    # ``date_derniere_reinscription + 365 j`` = prochaine échéance.
    # Soit on filtre par ``date_derniere_reinscription <= today - 365`` (overdue),
    # soit par ``today - 365 < date_derniere_reinscription <= today - (365 - lead)``
    # (due soon, fenêtre d'alerte douce).
    today = timezone.localdate()
    if (request.query_params.get("reinscription_overdue") or "").lower() in {"1", "true", "yes"}:
        qs = qs.filter(date_derniere_reinscription__lte=today - timedelta(days=365))
    raw_lead = request.query_params.get("reinscription_due_soon")
    if raw_lead:
        try:
            lead = int(raw_lead)
        except (TypeError, ValueError):
            lead = 0
        if lead > 0:
            anchor_lo = today - timedelta(days=365)
            anchor_hi = today - timedelta(days=365 - lead)
            qs = qs.filter(
                date_derniere_reinscription__gt=anchor_lo,
                date_derniere_reinscription__lte=anchor_hi,
            )

    from apps_coop.common import parse_pagination

    offset, limit = parse_pagination(
        request, default_limit=25, max_limit=_ADMIN_MEMBERS_PAGE_SIZE
    )
    count = qs.count()
    rows = qs[offset : offset + limit]
    return Response(
        {
            "count": count,
            "limit": limit,
            "offset": offset,
            "results": MemberReadSerializer(rows, many=True).data,
        }
    )


# ---------------------------------------------------------------------------
# BRC — Broad Range Consulting (LOT 1 refonte 2026)
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["members"],
    summary="Mes justificatifs BRC (refonte 2026)",
    description=(
        "GET — liste des `BRCDocument` du membre connecté (historique des "
        "uploads avec statut et motif de rejet éventuel). "
        "POST — dépose un nouveau justificatif (PDF / image). "
        "Permission : `IsMember`."
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsMember])
def brc_documents_me(request):
    member = request.user.member
    if request.method == "GET":
        qs = BRCDocument.objects.filter(member=member).order_by("-created_at")
        return Response(BRCDocumentReadSerializer(qs, many=True).data)

    serializer = BRCDocumentUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    fichier = serializer.validated_data["fichier"]
    doc = services.upload_brc_document(
        member=member,
        fichier=fichier,
        nom_original=serializer.validated_data.get("nom_original", "") or fichier.name,
        taille=fichier.size,
    )
    return Response(
        BRCDocumentReadSerializer(doc).data, status=status.HTTP_201_CREATED
    )


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — liste des justificatifs BRC à valider",
    description=(
        "Liste des `BRCDocument`. Filtre `?statut=en_attente|valide|rejete`. "
        "Permission : `IsStaff`."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_brc_documents(request):
    qs = BRCDocument.objects.select_related("member").order_by("-created_at")
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    return Response(
        BRCDocumentAdminReadSerializer(qs, many=True, context={"request": request}).data
    )


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — valider un justificatif BRC",
    description=(
        "Pose `BRCDocument.statut = valide`, met à jour `Member.is_brc_member`. "
        "Idempotent. Permission : `IsStaff`."
    ),
    responses={
        200: BRCDocumentAdminReadSerializer,
        400: OpenApiResponse(description="Document rejeté ou statut incompatible"),
        404: OpenApiResponse(description="Document introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_validate_brc_document(request, pk: int):
    try:
        doc = BRCDocument.objects.get(pk=pk)
    except BRCDocument.DoesNotExist:
        return Response(
            {"detail": "Document introuvable."}, status=status.HTTP_404_NOT_FOUND
        )
    try:
        services.validate_brc_document(doc=doc, validated_by=request.user)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    doc.refresh_from_db()
    return Response(
        BRCDocumentAdminReadSerializer(doc, context={"request": request}).data
    )


@extend_schema(
    tags=["members"],
    summary="🔒 Admin — rejeter un justificatif BRC",
    description=(
        "Pose `BRCDocument.statut = rejete` + `motif_rejet`. Le membre peut "
        "re-uploader. Permission : `IsStaff`."
    ),
    request=BRCDocumentRejectSerializer,
    responses={
        200: BRCDocumentAdminReadSerializer,
        400: OpenApiResponse(description="Motif vide ou statut incompatible"),
        404: OpenApiResponse(description="Document introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_reject_brc_document(request, pk: int):
    try:
        doc = BRCDocument.objects.get(pk=pk)
    except BRCDocument.DoesNotExist:
        return Response(
            {"detail": "Document introuvable."}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = BRCDocumentRejectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        services.reject_brc_document(
            doc=doc,
            rejected_by=request.user,
            motif=serializer.validated_data["motif"],
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    doc.refresh_from_db()
    return Response(
        BRCDocumentAdminReadSerializer(doc, context={"request": request}).data
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
    from decimal import Decimal

    from django.db.models import Sum

    from apps_coop.loans.models import (
        AvalisteConsent,
        JudicialEscalation,
        Loan,
        LoanFundingRequest,
        LoanRequest,
        MicrocreditCampaign,
    )
    from apps_coop.payments.models import Payment
    from apps_coop.payments.serializers import PaymentReadSerializer
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        LenderConsent,
        LenderTranche,
        SavingsAccount,
    )

    # --- Membres ---------------------------------------------------------
    members_active = Member.objects.filter(statut=Member.Statut.ACTIF).count()
    members_suspended = Member.objects.filter(statut=Member.Statut.SUSPENDU).count()
    members_temporaire = Member.objects.filter(
        statut=Member.Statut.TEMPORAIRE
    ).count()
    members_brc_validated = Member.objects.filter(
        statut=Member.Statut.ACTIF, is_brc_member=True
    ).count()

    # --- Files d'attente -------------------------------------------------
    pending_adhesions = MembershipRequest.objects.filter(
        statut=MembershipRequest.Statut.EN_ATTENTE
    ).count()
    loans_pending = LoanRequest.objects.filter(
        statut=LoanRequest.Statut.EN_INSTRUCTION
    ).count()
    avaliste_pending = AvalisteConsent.objects.filter(
        statut=AvalisteConsent.Statut.PENDING
    ).count()
    campaign_validation_pending = LoanRequest.objects.filter(
        statut=LoanRequest.Statut.EN_VALIDATION_CAMPAGNE
    ).count()

    # --- Finance ---------------------------------------------------------
    encours = (
        Loan.objects.filter(statut__in=[Loan.Statut.ACTIF, Loan.Statut.EN_RETARD])
        .aggregate(total=Sum("solde_restant"))["total"]
        or Decimal("0")
    )
    epargne_collecte = (
        SavingsAccount.objects.aggregate(total=Sum("solde"))["total"]
        or Decimal("0")
    )
    epargne_classique = (
        ClassicSavingsAccount.objects.aggregate(total=Sum("solde"))["total"]
        or Decimal("0")
    )
    epargne_total = Decimal(epargne_collecte) + Decimal(epargne_classique)

    # --- Épargne classique — état du cycle anniversaire (LOT 5) ----------
    classique_notifie = ClassicSavingsAccount.objects.filter(
        statut_renouvellement=ClassicSavingsAccount.StatutRenouvellement.NOTIFIE
    ).count()
    classique_urgence = ClassicSavingsAccount.objects.filter(
        statut_renouvellement=ClassicSavingsAccount.StatutRenouvellement.URGENCE
    ).count()
    classique_en_attente_paiement = ClassicSavingsAccount.objects.filter(
        statut_renouvellement=ClassicSavingsAccount.StatutRenouvellement.EN_ATTENTE_PAIEMENT
    ).count()

    # --- Prêteurs / funding (LOT 7-8) ------------------------------------
    lenders_active = LenderConsent.objects.filter(revoked_at__isnull=True).count()
    tranches_disponible = (
        LenderTranche.objects.filter(statut=LenderTranche.Statut.DISPONIBLE).aggregate(
            total=Sum("montant")
        )["total"]
        or Decimal("0")
    )
    tranches_engagee = (
        LenderTranche.objects.filter(statut=LenderTranche.Statut.ENGAGEE).aggregate(
            total=Sum("montant")
        )["total"]
        or Decimal("0")
    )
    funding_in_progress = LoanFundingRequest.objects.filter(
        statut__in=[
            LoanFundingRequest.Statut.PENDING,
            LoanFundingRequest.Statut.REALLOCATING,
        ]
    ).count()

    # --- Campagnes micro-crédit (LOT 11) ---------------------------------
    today = timezone.localdate()
    campaigns_active = MicrocreditCampaign.objects.filter(
        actif=True, date_debut__lte=today, date_fin__gte=today
    ).count()

    # --- Contentieux + escalades (LOT 13-14) -----------------------------
    loans_contentieux = Loan.objects.filter(
        statut=Loan.Statut.CONTENTIEUX
    ).count()
    loans_en_retard = Loan.objects.filter(statut=Loan.Statut.EN_RETARD).count()
    judicial_open = JudicialEscalation.objects.filter(
        statut__in=[
            JudicialEscalation.Statut.EN_INSTANCE,
            JudicialEscalation.Statut.DECISION_RENDUE,
        ]
    ).count()

    payments_recent = Payment.objects.filter(
        statut=Payment.Statut.VALIDE
    ).order_by("-date_validation")[:5]

    return Response(
        {
            "members": {
                "actif": members_active,
                "suspendu": members_suspended,
                "temporaire": members_temporaire,
                "brc_validated": members_brc_validated,
            },
            "queues": {
                "adhesions_en_attente": pending_adhesions,
                "credits_en_instruction": loans_pending,
                "avaliste_pending": avaliste_pending,
                "campaign_validation_pending": campaign_validation_pending,
            },
            "finance": {
                "encours_credit": str(encours),
                "epargne_total": str(epargne_total),
                "epargne_collecte": str(epargne_collecte),
                "epargne_classique": str(epargne_classique),
            },
            "epargne_classique_cycle": {
                "notifie": classique_notifie,
                "urgence": classique_urgence,
                "en_attente_paiement": classique_en_attente_paiement,
            },
            "lenders": {
                "consents_actifs": lenders_active,
                "tranches_disponible": str(tranches_disponible),
                "tranches_engagee": str(tranches_engagee),
                "funding_in_progress": funding_in_progress,
            },
            "campaigns": {
                "actives": campaigns_active,
            },
            "contentieux": {
                "loans_en_retard": loans_en_retard,
                "loans_contentieux": loans_contentieux,
                "escalades_ouvertes": judicial_open,
            },
            "recent_payments": PaymentReadSerializer(payments_recent, many=True).data,
        }
    )
