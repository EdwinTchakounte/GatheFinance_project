"""Loans HTTP endpoints — member-facing surface (UC3 step A).

Admin endpoints (instruct / decide / counter / disburse) will follow once the
Next.js admin is up. In the meantime the Django admin in
``/django-admin/loans/loanrequest/`` is sufficient for staff use.
"""
from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import client_ip, record as record_audit
from apps_coop.members.permissions import IsActiveMember, IsAdmin, IsComite, IsMember, IsStaff
from apps_coop.payments.models import FeeType, Payment

from .models import Loan, LoanRequest
from .serializers import (
    LoanDisburseSerializer,
    LoanReadSerializer,
    LoanRenewalDecideSerializer,
    LoanRenewalReadSerializer,
    LoanRenewalRequestSerializer,
    LoanRequestDecideSerializer,
    LoanRequestReadSerializer,
    LoanRequestSubmitSerializer,
)
from .services import (
    approve_loan_renewal,
    approve_loan_request,
    compute_eligibility,
    disburse_loan_manual,
    disburse_loan_via_tara,
    reject_loan_renewal,
    reject_loan_request,
    request_loan_renewal,
)
from apps_coop.payments.providers.base import ProviderError


# ---------------------------------------------------------------------------
# 1. GET /api/v1/loans/me/eligibility/ — can I submit a new request?
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="Éligibilité du membre à demander un crédit",
    description=(
        "Retourne `{ eligible, plafond_max, motifs_ineligibilite, solde_epargne, "
        "ratio_garantie }`. Plafond = solde épargne × 10. Bloquant si : statut "
        "non actif, prêt actif/en_retard, demande déjà en cours, solde < 100 XAF."
    ),
    responses={200: OpenApiResponse(description="Détail éligibilité")},
)
@api_view(["GET"])
@permission_classes([IsMember])
def loan_eligibility(request):
    member = request.user.member
    e = compute_eligibility(member)
    return Response(
        {
            "eligible": e.eligible,
            "plafond_max": str(e.plafond_max),
            "motifs_ineligibilite": e.motifs,
            "solde_epargne": str(e.solde_epargne),
            "ratio_garantie": str(e.ratio_garantie),
        }
    )


# ---------------------------------------------------------------------------
# 2. POST /api/v1/loans/requests/ — submit a new credit request
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="Soumettre une demande de crédit",
    description=(
        "Crée une `LoanRequest` (statut `en_attente`) + génère le montant des frais "
        "de dossier à payer ensuite via `/payments/init/` (type `frais_demande_credit`). "
        "Validation : éligibilité, montant in [5000, plafond], durée in [3, 36] mois."
    ),
    request=LoanRequestSubmitSerializer,
    responses={
        201: OpenApiResponse(description="`{ loan_request, frais_a_payer }`"),
        400: OpenApiResponse(description="Montant ou durée hors limites"),
        403: OpenApiResponse(description="Non éligible (statut, prêt existant, solde…)"),
        503: OpenApiResponse(description="FeeType DEMANDE_CREDIT non configuré"),
    },
)
@api_view(["POST"])
@permission_classes([IsActiveMember])
def loan_request_create(request):
    member = request.user.member
    eligibility = compute_eligibility(member)
    if not eligibility.eligible:
        return Response(
            {"detail": "Non éligible.", "motifs": eligibility.motifs},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = LoanRequestSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # The plafond is recomputed server-side — frontend value is informational.
    if data["montant_demande"] > eligibility.plafond_max:
        return Response(
            {
                "detail": (
                    f"Montant demandé ({data['montant_demande']} XAF) supérieur "
                    f"au plafond éligible ({eligibility.plafond_max} XAF)."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Lookup the current adhesion fee from FeeType — admin-editable.
    try:
        fee = FeeType.objects.get(code=FeeType.Code.DEMANDE_CREDIT, actif=True)
        frais_montant = fee.montant
    except FeeType.DoesNotExist:
        return Response(
            {"detail": "Frais de demande de crédit non configurés."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    with transaction.atomic():
        loan_request = LoanRequest.objects.create(
            member=member,
            montant_demande=data["montant_demande"],
            duree_mois=data["duree_mois"],
            motif=data["motif"],
            statut=LoanRequest.Statut.EN_ATTENTE,
        )
        # Frais de dossier — Payment row created in 'en_attente'. Le membre
        # devra ensuite passer par le flow 01 (/payments/init/) pour confirmer.
        # On garde la création séparée pour rester aligné sur le pattern
        # « init/ déclenche la gateway ». Ici on ne crée rien côté Tara.
        record_audit(
            action="loan_request.submitted",
            entite_type="LoanRequest",
            entite_id=loan_request.id,
            user=request.user,
            details={
                "montant_demande": str(loan_request.montant_demande),
                "duree_mois": loan_request.duree_mois,
                "frais_a_payer": str(frais_montant),
            },
            ip=client_ip(request),
        )

    return Response(
        {
            "loan_request": LoanRequestReadSerializer(loan_request).data,
            "frais_a_payer": {
                "code": "DEMANDE_CREDIT",
                "libelle": "Frais de demande de crédit",
                "montant": str(frais_montant),
            },
        },
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# 3. GET /api/v1/loans/me/requests/ — list my own requests
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="Mes demandes de crédit (historique)",
    description="Toutes les `LoanRequest` du membre, ordre antéchronologique.",
    responses={200: LoanRequestReadSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsMember])
def loan_request_list(request):
    qs = LoanRequest.objects.filter(member=request.user.member).order_by("-date_soumission")
    return Response(LoanRequestReadSerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# 4. GET /api/v1/loans/me/active/ — current member's active credits
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — liste des demandes de crédit",
    description="Accepte `?statut=en_instruction|approuvee|rejetee|en_attente`.",
    responses={200: LoanRequestReadSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_loan_requests(request):
    qs = LoanRequest.objects.order_by("-date_soumission")
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    return Response(LoanRequestReadSerializer(qs, many=True).data)


@extend_schema(
    tags=["loans"],
    summary="🔒 Comité — décision sur une demande en instruction",
    description=(
        "Permission : groupe `comite` ou superuser. La demande doit être en "
        "statut `en_instruction` (frais payés). `decision=approuvee` crée le "
        "`Loan` + échéancier complet ; `decision=rejetee` ferme la demande."
    ),
    request=LoanRequestDecideSerializer,
    responses={
        200: LoanRequestReadSerializer,
        400: OpenApiResponse(description="Validation rejetée ou demande pas en instruction"),
        404: OpenApiResponse(description="Demande introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsComite])
def loan_request_decide(request, pk: int):
    try:
        loan_request = LoanRequest.objects.get(pk=pk)
    except LoanRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    serializer = LoanRequestDecideSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        if data["decision"] == "approuvee":
            approve_loan_request(
                loan_request,
                decided_by=request.user,
                taux_annuel=data["taux_annuel"],
                date_premiere_echeance=data["date_premiere_echeance"],
            )
        else:
            reject_loan_request(loan_request, decided_by=request.user, motif=data["motif_rejet"])
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    loan_request.refresh_from_db()
    return Response(LoanRequestReadSerializer(loan_request).data)


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — décaissement d'un crédit approuvé",
    description=(
        "Permission : groupe `admin` ou superuser. Deux modes :\n\n"
        "- `mode=manuel` (par défaut) — crée un Payment `valide` qui atteste "
        "  qu'on a viré l'argent au membre par virement bancaire ou espèces. "
        "  Requis : `reference_externe`.\n"
        "- `mode=tara` — déclenche un payout Mobile Money via Tara. Crée un "
        "  Payment `en_attente` ; le webhook Tara passera à `valide` et "
        "  déclenchera `_hook_decaissement`. Requis : `recipient_phone` + `network`.\n\n"
        "Idempotent dans les 2 modes : si un Payment décaissement existe déjà "
        "(`valide` ou `en_attente`), on le retourne sans nouvel appel."
    ),
    request=LoanDisburseSerializer,
    responses={
        200: OpenApiResponse(description="Payment de décaissement créé/existant"),
        400: OpenApiResponse(description="Loan pas en statut actif ou paramètres invalides"),
        404: OpenApiResponse(description="Loan introuvable"),
        502: OpenApiResponse(description="Erreur Tara non réessayable"),
        503: OpenApiResponse(description="Tara indisponible (retryable)"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def loan_disburse(request, pk: int):
    try:
        loan = Loan.objects.get(pk=pk)
    except Loan.DoesNotExist:
        return Response({"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if loan.statut not in (Loan.Statut.ACTIF, Loan.Statut.EN_RETARD):
        return Response(
            {"detail": f"Crédit en statut {loan.statut!r} — décaissement impossible."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = LoanDisburseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    mode = data.get("mode", "manuel")

    if mode == "tara":
        try:
            payment = disburse_loan_via_tara(
                loan,
                agent=request.user,
                recipient_phone=data["recipient_phone"],
                network=data["network"],
            )
        except ProviderError as exc:
            http_status = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if exc.retryable
                else status.HTTP_502_BAD_GATEWAY
            )
            return Response(
                {"detail": f"Tara indisponible : {exc}"},
                status=http_status,
            )
    else:
        payment = disburse_loan_manual(
            loan,
            agent=request.user,
            reference_externe=data["reference_externe"],
            note=data.get("note", ""),
        )

    return Response(
        {
            "loan_id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "payment_id": payment.id,
            "mode": mode,
            "statut": payment.statut,
            "reference_externe": payment.reference_externe,
        }
    )


@extend_schema(
    tags=["loans"],
    summary="Mes crédits en cours (avec échéancier)",
    description=(
        "Loans non clôturés du membre (`actif`, `en_retard`, `contentieux`), avec "
        "le tableau d'amortissement complet (`installments[]`). Pour le MVP : "
        "au plus 1 entrée — règle d'éligibilité empêche d'avoir 2 prêts simultanés."
    ),
    responses={200: LoanReadSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsMember])
def loans_me_active(request):
    """Return all Loans that are still owed by the member (any non-cloture
    statut), with their full installment schedule.

    For the MVP a member can only have one active Loan at a time (enforced by
    ``compute_eligibility``), so the list will contain 0 or 1 entry.
    """
    qs = (
        Loan.objects.filter(member=request.user.member)
        .exclude(statut=Loan.Statut.CLOTURE)
        .prefetch_related("installments")
        .order_by("-date_decaissement")
    )
    return Response(LoanReadSerializer(qs, many=True).data)


@extend_schema(
    tags=["loans"],
    summary="Demander la reconduction d'un crédit en cours",
    description=(
        "Crée une `LoanRenewal(statut=demandee)` pour le crédit indiqué. "
        "Permission : `IsActiveMember` (compte membre actif). Le membre paie "
        "ensuite les frais de reconduction via "
        "`POST /api/v1/payments/init/` (type=`frais_reconduction`) ; le hook "
        "`_hook_loan_renewal_fees` rattachera automatiquement le Payment à la "
        "LoanRenewal. Le comité statue ensuite depuis Django admin.\n\n"
        "Idempotent : si une renewal `demandee` existe déjà pour ce crédit, "
        "elle est retournée telle quelle (pas de doublon)."
    ),
    request=LoanRenewalRequestSerializer,
    responses={
        201: LoanRenewalReadSerializer,
        400: OpenApiResponse(description="Crédit pas en statut actif/en_retard, ou durée hors plage"),
        403: OpenApiResponse(description="Crédit n'appartient pas au membre"),
        404: OpenApiResponse(description="Crédit introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsActiveMember])
def loan_renewal_request(request, pk: int):
    member = request.user.member
    try:
        loan = Loan.objects.get(pk=pk, member=member)
    except Loan.DoesNotExist:
        return Response({"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND)

    serializer = LoanRenewalRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        renewal = request_loan_renewal(
            loan,
            nouvelle_duree_mois=serializer.validated_data.get("nouvelle_duree_mois"),
            interets_au_comptant=serializer.validated_data.get(
                "interets_au_comptant", False
            ),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    record_audit(
        action="loan_renewal.requested",
        entite_type="LoanRenewal",
        entite_id=renewal.id,
        user=request.user,
        details={
            "loan_id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "nouvelle_duree_mois": renewal.nouvelle_duree_mois,
        },
        ip=client_ip(request),
    )

    # On renvoie aussi le montant des frais à payer (lecture FeeType admin-editable).
    from apps_coop.payments.models import FeeType

    fee = FeeType.objects.filter(code=FeeType.Code.RECONDUCTION, actif=True).first()
    payload = LoanRenewalReadSerializer({
        "id": renewal.id,
        "loan_id": loan.id,
        "nouvelle_duree_mois": renewal.nouvelle_duree_mois,
        "statut": renewal.statut,
        "date_demande": renewal.date_demande,
        "frais_reconduction_payment_id": renewal.frais_reconduction_payment_id,
    }).data
    return Response(
        {
            "renewal": payload,
            "frais_a_payer": {
                "code": "RECONDUCTION",
                "libelle": fee.libelle if fee else "Frais de reconduction",
                "montant": str(fee.montant) if fee else "0",
            } if fee else None,
        },
        status=status.HTTP_201_CREATED,
    )


_ADMIN_LOANS_PAGE_SIZE = 200


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — liste des crédits",
    description=(
        "Liste paginée de tous les `Loan` pour le dashboard admin. Filtres : "
        "`?statut=actif|en_retard|cloture|contentieux`, `?member=<id>`, "
        "`?q=<numero_dossier|numero_membre|nom>`."
    ),
    responses={200: OpenApiResponse(description="`{ count, results: Loan[] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_loans(request):
    qs = (
        Loan.objects.select_related("member", "member__user")
        .prefetch_related("installments")
        .order_by("-date_decaissement")
    )
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    member_id = request.query_params.get("member")
    if member_id:
        qs = qs.filter(member_id=member_id)
    q = (request.query_params.get("q") or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(numero_dossier__icontains=q)
            | Q(member__numero_membre__icontains=q)
            | Q(member__nom__icontains=q)
            | Q(member__prenom__icontains=q)
        )

    count = qs.count()
    rows = qs[:_ADMIN_LOANS_PAGE_SIZE]
    results = []
    for loan in rows:
        nb_payees = sum(1 for i in loan.installments.all() if i.statut == "payee")
        nb_total = loan.installments.count()
        results.append({
            "id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "member": {
                "id": loan.member_id,
                "numero_membre": loan.member.numero_membre,
                "nom": loan.member.nom,
                "prenom": loan.member.prenom,
            },
            "montant": str(loan.montant),
            "montant_total_du": str(loan.montant_total_du),
            "solde_restant": str(loan.solde_restant),
            "taux_interet": str(loan.taux_interet),
            "duree_mois": loan.duree_mois,
            "date_decaissement": loan.date_decaissement.isoformat(),
            "date_premiere_echeance": loan.date_premiere_echeance.isoformat(),
            "statut": loan.statut,
            "statut_display": loan.get_statut_display(),
            "installments_payees": nb_payees,
            "installments_total": nb_total,
        })
    return Response({"count": count, "results": results})


@extend_schema(
    tags=["loans"],
    summary="🔒 Comité — décide d'une demande de reconduction",
    description=(
        "Permission : `IsComite` (groupe `comite`) ou superuser. Deux issues possibles :\n\n"
        "- `decision=approuvee` (requis : `taux_annuel`, `date_premiere_echeance`) — "
        "  clôture l'ancien crédit, crée le nouveau crédit avec le solde repris + le "
        "  nouvel échéancier, et envoie l'email `loan_renewal.approved`.\n"
        "- `decision=rejetee` (requis : `motif_rejet`) — pose `statut=rejetee` + motif "
        "  + email `loan_renewal.rejected`."
    ),
    request=LoanRenewalDecideSerializer,
    responses={
        200: OpenApiResponse(description="Décision enregistrée"),
        400: OpenApiResponse(description="Statut incompatible / frais non payés / taux invalide"),
        404: OpenApiResponse(description="Reconduction introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsComite])
def loan_renewal_decide(request, pk: int):
    from .models import LoanRenewal

    try:
        renewal = LoanRenewal.objects.select_related("loan", "loan__member__user").get(pk=pk)
    except LoanRenewal.DoesNotExist:
        return Response({"detail": "Reconduction introuvable."}, status=status.HTTP_404_NOT_FOUND)

    serializer = LoanRenewalDecideSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        if data["decision"] == "approuvee":
            nouveau_loan = approve_loan_renewal(
                renewal,
                decided_by=request.user,
                taux_annuel=data["taux_annuel"],
                date_premiere_echeance=data["date_premiere_echeance"],
            )
            return Response(
                {
                    "decision": "approuvee",
                    "ancien_dossier": renewal.loan.numero_dossier,
                    "nouveau_dossier": nouveau_loan.numero_dossier,
                    "nouveau_loan_id": nouveau_loan.id,
                    "montant_total_du": str(nouveau_loan.montant_total_du),
                }
            )
        else:
            reject_loan_renewal(
                renewal,
                decided_by=request.user,
                motif=data["motif_rejet"],
            )
            return Response(
                {
                    "decision": "rejetee",
                    "renewal_id": renewal.id,
                    "motif": data["motif_rejet"],
                }
            )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — émettre une mise en demeure (Article 13)",
    description=(
        "Émet une mise en demeure sur un crédit en retard ou en contentieux. "
        "Horodate, incrémente le compteur, trace l'audit et notifie le membre. "
        "Permission : `IsStaff`."
    ),
    responses={
        200: OpenApiResponse(description="Mise en demeure enregistrée"),
        400: OpenApiResponse(description="Crédit pas en retard/contentieux"),
        404: OpenApiResponse(description="Crédit introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsStaff])
def loan_notice(request, pk: int):
    try:
        loan = Loan.objects.select_related("member", "member__user").get(pk=pk)
    except Loan.DoesNotExist:
        return Response({"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if loan.statut not in (Loan.Statut.EN_RETARD, Loan.Statut.CONTENTIEUX):
        return Response(
            {"detail": "Une mise en demeure ne s'émet que sur un crédit en retard ou en contentieux."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    loan.mise_en_demeure_at = timezone.now()
    loan.mise_en_demeure_count = (loan.mise_en_demeure_count or 0) + 1
    loan.save(update_fields=["mise_en_demeure_at", "mise_en_demeure_count", "updated_at"])

    record_audit(
        action="loan.notice_issued",
        entite_type="Loan",
        entite_id=loan.id,
        user=request.user,
        details={
            "numero_dossier": loan.numero_dossier,
            "count": loan.mise_en_demeure_count,
            "statut": loan.statut,
            "solde_restant": str(loan.solde_restant),
        },
        ip=client_ip(request),
    )

    from django.conf import settings as dj_settings

    from apps_coop.notifications.services import send_template

    member = loan.member
    if getattr(member.user, "email", None):
        try:
            send_template(
                "loan.notice",
                to=member.user.email,
                member=member,
                context={
                    "prenom": member.prenom,
                    "numero_dossier": loan.numero_dossier,
                    "solde_restant": f"{int(loan.solde_restant):,}".replace(",", " "),
                    "count": loan.mise_en_demeure_count,
                    "portal_url": getattr(dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
                },
            )
        except Exception:  # noqa: BLE001
            pass

    return Response(
        {
            "id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "statut": loan.statut,
            "mise_en_demeure_at": loan.mise_en_demeure_at.isoformat(),
            "mise_en_demeure_count": loan.mise_en_demeure_count,
        }
    )
