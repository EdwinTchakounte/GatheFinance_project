"""Loans HTTP endpoints — member-facing surface (UC3 step A).

Admin endpoints (instruct / decide / counter / disburse) will follow once the
Next.js admin is up. In the meantime the Django admin in
``/django-admin/loans/loanrequest/`` is sufficient for staff use.
"""
from __future__ import annotations


from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import client_ip, record as record_audit
from apps_coop.members.permissions import (
    IsActiveMember,
    IsAdmin,
    IsComite,
    IsMember,
    IsStaff,
    ResourceAccess,
)
from apps_coop.payments.models import FeeType, Payment

from .models import Loan, LoanRequest
from .serializers import (
    AdminLoanRequestReadSerializer,
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
        "Retourne `{ eligible, plafond_max, plafond_sans_avaliste, "
        "motifs_ineligibilite, solde_epargne, ratio_garantie }`. Réforme 2026 : "
        "le montant est LIBRE. `plafond_sans_avaliste` = épargne classique "
        "disponible (montant max empruntable en auto-couverture) ; au-delà, "
        "désigner un avaliste. Bloquant seulement si : statut non actif, prêt "
        "actif/en_retard, ou demande déjà en cours."
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
            # Rétro-compat : plafond_max == plafond sans avaliste (indicatif,
            # plus un cap dur côté client depuis la réforme montant libre).
            "plafond_max": str(e.plafond_max),
            "plafond_sans_avaliste": str(e.plafond_max),
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
def _universal_blockers(member) -> list[str]:
    """Pré-checks communs aux 3 voies (refonte 2026 LOT 15).

    Ce qui était dans ``compute_eligibility`` mais qui s'applique
    indépendamment de la voie :
      - statut membre ACTIF ou TEMPORAIRE (les TEMPORAIRE sont les
        bénéficiaires d'une campagne en cours, pas autorisés à empiler).
      - pas de crédit ACTIF / EN_RETARD / CONTENTIEUX
      - pas de demande en cours (legacy + nouveaux statuts 2026)

    Le check "solde ≥ 100 XAF" est volontairement omis : il appartient à
    la voie 1 (SENIOR_BRC) qui implicite une épargne minimale. Voies 2/3
    n'ont pas ce critère.
    """
    from apps_coop.members.models import Member

    blockers: list[str] = []
    if member.statut not in {Member.Statut.ACTIF, Member.Statut.TEMPORAIRE}:
        blockers.append("Compte membre non actif.")
    active_loans = Loan.objects.filter(
        member=member,
        statut__in=[
            Loan.Statut.ACTIF,
            Loan.Statut.EN_RETARD,
            Loan.Statut.CONTENTIEUX,
        ],
    ).count()
    if active_loans:
        blockers.append(
            f"Vous avez déjà {active_loans} crédit(s) en cours. "
            "Terminez-les avant d'en demander un nouveau."
        )
    pending = LoanRequest.objects.filter(
        member=member,
        statut__in=[
            LoanRequest.Statut.EN_ATTENTE,
            LoanRequest.Statut.EN_INSTRUCTION,
            LoanRequest.Statut.EN_ATTENTE_ACCEPTATION_MEMBRE,
            LoanRequest.Statut.EN_ATTENTE_AVALISTE,
            LoanRequest.Statut.EN_VALIDATION_CAMPAGNE,
            # Approuvée provisoirement (attente visite terrain) = toujours en
            # cours → bloque une 2e demande parallèle.
            LoanRequest.Statut.APPROUVEE_PROVISOIRE,
        ],
    ).count()
    if pending:
        blockers.append(
            "Vous avez déjà une demande de crédit en cours. "
            "Attendez la décision avant d'en soumettre une nouvelle."
        )
    return blockers


@api_view(["POST"])
@permission_classes([IsActiveMember])
def loan_request_create(request):
    """Soumission d'une demande de crédit (refonte 2026 LOT 15).

    Pipeline :
      1. Pré-checks universels (statut, crédit en cours, demande en cours).
      2. Routage 3 voies via ``evaluate_routes`` (LOT 12) :
         - SENIOR_BRC → plafond legacy (solde × 10) → statut EN_ATTENTE
         - AVALISTE   → ``request_avaliste_consent`` → statut EN_ATTENTE_AVALISTE
         - CAMPAIGN   → FK ``microcampaign`` posée → statut EN_VALIDATION_CAMPAGNE
         - NONE       → 403 avec motifs cumulés
    """
    member = request.user.member
    from .eligibility_routing import EligibilityRoute, evaluate_routes
    from .models import MicrocreditCampaign

    serializer = LoanRequestSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # 1) Pré-checks universels — communs aux 3 voies.
    blockers = _universal_blockers(member)
    if blockers:
        record_audit(
            action="loan_request.refused_universal",
            entite_type="Member",
            entite_id=member.id,
            user=request.user,
            details={"motifs": blockers},
            ip=client_ip(request),
        )
        return Response(
            {"detail": "Vous ne pouvez pas soumettre de demande.", "motifs": blockers},
            status=status.HTTP_403_FORBIDDEN,
        )

    # 2) Routage 3 voies. extra_payload contient les flags BRC declares
    # sur le formulaire (cga_brc_member, cfp_brc_apprenant) qui peuvent
    # debloquer la Voie 1 SENIOR_BRC sans validation admin prealable.
    route_eval = evaluate_routes(
        member,
        montant=data["montant_demande"],
        avaliste_numero=data.get("avaliste_numero") or None,
        avaliste_nom=data.get("avaliste_nom") or None,
        campaign_id=data.get("campaign_id"),
        profil_cible=data.get("profil_cible") or None,
        garantie_materielle=bool(data.get("garantie_materielle")),
        extra_payload=data.get("extra_payload") or {},
    )

    if not route_eval.eligible:
        record_audit(
            action="loan_request.refused_no_route",
            entite_type="Member",
            entite_id=member.id,
            user=request.user,
            details={
                "motifs": route_eval.motifs,
                "suggested_campaigns": route_eval.suggested_campaigns,
            },
            ip=client_ip(request),
        )
        return Response(
            {
                "detail": "Aucune voie d'éligibilité ne s'applique à votre demande.",
                "motifs": route_eval.motifs,
                "suggested_campaigns": route_eval.suggested_campaigns,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # 3) Réforme garantie 2026 : plus de plafond ×10. Le montant est libre ;
    # la voie retenue garantit déjà la couverture (auto-couverture : épargne
    # dispo ≥ montant ; avaliste : épargne dem+aval ≥ montant ; campagne :
    # bornes campagne). Rien à re-vérifier ici.

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
        # Statut initial + FK selon la voie.
        if route_eval.route == EligibilityRoute.CAMPAIGN:
            initial_statut = LoanRequest.Statut.EN_VALIDATION_CAMPAGNE
            campaign_fk = MicrocreditCampaign.objects.get(
                pk=route_eval.details["campaign_id"]
            )
        else:
            initial_statut = LoanRequest.Statut.EN_ATTENTE
            campaign_fk = None

        # CH-4 — Champs ajoutés via FormSchema → extra_payload.
        try:
            from apps_coop.forms.services import apply_form_schema

            _LOAN_REQUEST_HARDCODED = {
                "montant_demande", "duree_mois", "motif",
                "modalite_paiement",
                # Voies AVALISTE / CAMPAIGN — toujours en colonnes/relations.
                "avaliste_numero", "avaliste_nom",
                "campaign_id", "profil_cible",
                # L4/L5 — garantie matérielle + n° CNI demandeur.
                "garantie_materielle", "garantie_description",
                "cni_demandeur",
            }
            _, extra_payload, schema_version = apply_form_schema(
                "loan_request",
                {k: v for k, v in request.data.items()},
                hardcoded_keys=_LOAN_REQUEST_HARDCODED,
            )
        except Exception:  # noqa: BLE001 — legacy fallback
            import logging
            logging.getLogger(__name__).exception(
                "apply_form_schema('loan_request') failed — falling back to legacy",
            )
            extra_payload, schema_version = {}, None

        # Compat layer démo NHR — assure que les réponses CFP Broad Range et
        # CGA sont stockées en BD même si le seed FormSchema en prod n'a pas
        # encore été poussé avec ces champs (apply_form_schema filtre sinon
        # les valeurs inconnues). Le mobile envoie ces clés systématiquement.
        for compat_key in ("ancien_apprenant", "cga_adherent"):
            val = request.data.get(compat_key)
            if val in ("oui", "non") and compat_key not in extra_payload:
                extra_payload[compat_key] = val

        # Voie 1 (SENIOR_BRC) : le demandeur gèle sa propre épargne à hauteur de
        # ``min(montant, épargne disponible)``. En auto-couverture c'est = montant ;
        # pour un ANCIEN+BRC sous-couvert c'est son épargne dispo (il immobilise
        # ce qu'il a, le reste est un crédit de confiance jugé par le comité).
        # Voie avaliste : posé par request_avaliste_consent (le manque). Campagne : 0.
        if route_eval.route == EligibilityRoute.SENIOR_BRC:
            from .avaliste_services import _member_available_savings

            _dispo = _member_available_savings(member)
            gel_demandeur_initial = min(data["montant_demande"], _dispo)
        else:
            gel_demandeur_initial = 0

        is_garantie_mat = route_eval.route == EligibilityRoute.GARANTIE_MATERIELLE

        # L6 — Échéance indicative d'étude commission (soumission + délai max).
        from datetime import timedelta as _timedelta

        from apps_coop.audit.services import get_int_setting

        _study_days = get_int_setting("loans.study.max_days", 30)
        date_limite_etude = timezone.localdate() + _timedelta(days=_study_days)

        loan_request = LoanRequest.objects.create(
            member=member,
            montant_demande=data["montant_demande"],
            duree_mois=data["duree_mois"],
            motif=data["motif"],
            statut=initial_statut,
            microcampaign=campaign_fk,
            montant_gele_demandeur=gel_demandeur_initial,
            # L6 — échéance indicative d'étude commission.
            date_limite_etude=date_limite_etude,
            # L5 — n° CNI du demandeur (saisi à la soumission).
            cni_demandeur=(data.get("cni_demandeur") or "").strip(),
            # L4 — garantie matérielle (le titre est uploadé en attachment).
            garantie_materielle=is_garantie_mat,
            garantie_description=(
                (data.get("garantie_description") or "").strip()
                if is_garantie_mat
                else ""
            ),
            extra_payload=extra_payload,
            form_schema_version=schema_version,
            # CH-9 — Canal de réception choisi à la soumission.
            moyen_reception=data.get("moyen_reception") or "",
            recipient_phone=(data.get("recipient_phone") or "").strip(),
        )

        # Auto-couverture : projette le gel du demandeur sur ses tranches de
        # placement (elles sortent du pool prêteur). La voie avaliste fait la
        # même chose depuis request_avaliste_consent, avec son propre montant.
        if gel_demandeur_initial:
            from .guarantee_tranches import earmark_guarantee_tranches

            earmark_guarantee_tranches(
                member=member,
                montant=gel_demandeur_initial,
                loan_request=loan_request,
            )

        # Voie AVALISTE — « frais d'abord, avaliste ensuite » : on mémorise la
        # désignation, on ne sollicite personne. Le consentement est posé par
        # open_instruction_after_fees, une fois les frais encaissés.
        if route_eval.route == EligibilityRoute.AVALISTE:
            loan_request.avaliste_numero_saisi = data["avaliste_numero"].strip()
            loan_request.avaliste_nom_saisi = data["avaliste_nom"].strip()
            loan_request.save(
                update_fields=[
                    "avaliste_numero_saisi",
                    "avaliste_nom_saisi",
                    "updated_at",
                ]
            )
            # Étude gratuite → rien à encaisser, on enchaîne tout de suite.
            if frais_montant <= 0:
                from .study_fee_services import open_instruction_after_fees

                open_instruction_after_fees(loan_request)

        record_audit(
            action="loan_request.submitted",
            entite_type="LoanRequest",
            entite_id=loan_request.id,
            user=request.user,
            details={
                "montant_demande": str(loan_request.montant_demande),
                "duree_mois": loan_request.duree_mois,
                "route": route_eval.route,
                "route_details": route_eval.details,
                "frais_a_payer": str(frais_montant),
            },
            ip=client_ip(request),
        )

    # Accusé de réception (best-effort — ne bloque pas la création).
    if getattr(member.user, "email", None):
        try:
            from django.conf import settings as dj_settings

            from apps_coop.notifications.events import emit_event

            emit_event(
                "loan_request.submitted",
                member=member,
                context={
                    "prenom": member.prenom,
                    "montant": f"{int(loan_request.montant_demande):,}".replace(",", " "),
                    "frais_montant": f"{int(frais_montant):,}".replace(",", " "),
                    "portal_url": getattr(
                        dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"
                    ),
                },
            )
        except Exception:  # noqa: BLE001
            pass

    # Re-charge pour récupérer le statut potentiellement modifié par la
    # voie AVALISTE (request_avaliste_consent passe en EN_ATTENTE_AVALISTE).
    loan_request.refresh_from_db()
    # CH-7 — Mention non-remboursable explicite (configurable via AppSetting).
    from apps_coop.audit.services import get_str_setting
    non_refundable_notice = get_str_setting(
        "loans.study_fee.non_refundable_notice",
        "Ces frais d'étude couvrent l'instruction du dossier et la visite "
        "terrain éventuelle. Ils sont non-remboursables, y compris en cas "
        "de refus de la demande.",
    )

    return Response(
        {
            "loan_request": LoanRequestReadSerializer(loan_request).data,
            "route": route_eval.route,
            "route_details": route_eval.details,
            "frais_a_payer": {
                "code": "DEMANDE_CREDIT",
                "libelle": "Frais d'étude du dossier",
                "montant": str(frais_montant),
                # CH-7 — Information UI : ces frais sont non-remboursables.
                "non_remboursable": True,
                "notice": non_refundable_notice,
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
# Transfert — rembourser un crédit depuis l'épargne (G6, refonte 2026-07)
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="Argent disponible pour un transfert (remboursement)",
    description=(
        "Somme mobilisable pour rembourser un crédit : épargne classique "
        "retirable (hors placement/gel) + collecte."
    ),
)
@api_view(["GET"])
@permission_classes([IsActiveMember])
def transfer_available(request):
    from .transfer_services import available_for_transfer

    data = available_for_transfer(request.user.member)
    return Response({k: str(v) for k, v in data.items()})


@extend_schema(
    tags=["loans"],
    summary="Transférer de l'épargne vers un crédit (remboursement)",
    description=(
        "Rembourse `montant` sur le crédit `pk` du membre en puisant dans son "
        "épargne classique retirable puis sa collecte. Transfert interne "
        "(pas de Mobile Money)."
    ),
)
@api_view(["POST"])
@permission_classes([IsActiveMember])
def loan_repay_from_savings(request, pk: int):
    from decimal import Decimal, InvalidOperation

    from .transfer_services import TransferError, repay_loan_from_savings

    loan = Loan.objects.filter(pk=pk, member=request.user.member).first()
    if loan is None:
        return Response({"detail": "Crédit introuvable."}, status=404)
    try:
        montant = Decimal(str(request.data.get("montant")))
    except (InvalidOperation, TypeError):
        return Response({"detail": "Montant invalide."}, status=400)
    try:
        payment = repay_loan_from_savings(loan, montant)
    except TransferError as exc:
        return Response({"detail": str(exc)}, status=400)
    loan.refresh_from_db()
    return Response(
        {
            "payment_id": payment.id,
            "montant": str(payment.montant),
            "solde_restant": str(loan.solde_restant),
            "statut": loan.statut,
        }
    )


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
    # Filtre membre — utilisé par la saisie de versement (cash-in) pour
    # retrouver la demande de crédit d'un adhérent et encaisser ses frais.
    member_id = request.query_params.get("member")
    if member_id:
        qs = qs.filter(member_id=member_id)
    # Admin/staff : serializer étendu (visite terrain incluse).
    return Response(AdminLoanRequestReadSerializer(qs, many=True).data)


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
        from .services import tara_payout_enabled

        if not tara_payout_enabled():
            return Response(
                {"detail": "Payout Tara désactivé. Effectuez le virement sur Tara puis enregistrez le décaissement en mode « manuel » (avec la référence)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
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


# P3 . Historique des credits cloturees (parite mobile cote portail web).
@extend_schema(
    tags=["loans"],
    summary="Mes crédits clôturés (historique)",
    description=(
        "Loans `statut=cloture` du membre, plus recents d'abord. "
        "Inclut l'echeancier complet pour affichage de l'historique "
        "des remboursements ligne a ligne."
    ),
    responses={200: LoanReadSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsMember])
def loans_me_closed(request):
    qs = (
        Loan.objects.filter(
            member=request.user.member,
            statut=Loan.Statut.CLOTURE,
        )
        # Le membre a pu masquer certains crédits clôturés de sa vue.
        .exclude(masque_par_membre=True)
        .prefetch_related("installments")
        .order_by("-date_decaissement")
    )
    return Response(LoanReadSerializer(qs, many=True).data)


@extend_schema(
    tags=["loans"],
    summary="Masquer un crédit clôturé de sa vue (soft-hide membre)",
    description=(
        "Le membre retire un crédit CLÔTURÉ de sa liste (mobile/portail). "
        "RIEN n'est supprimé en base : l'admin, l'audit et la compta le voient "
        "toujours. Idempotent. Seul un crédit clôturé peut être masqué."
    ),
    responses={
        200: OpenApiResponse(description="Crédit masqué"),
        400: OpenApiResponse(description="Le crédit n'est pas clôturé"),
        404: OpenApiResponse(description="Crédit introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsMember])
def loan_me_hide(request, pk: int):
    loan = Loan.objects.filter(pk=pk, member=request.user.member).first()
    if loan is None:
        return Response(
            {"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND
        )
    if loan.statut != Loan.Statut.CLOTURE:
        return Response(
            {"detail": "Seul un crédit clôturé peut être masqué."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not loan.masque_par_membre:
        loan.masque_par_membre = True
        loan.save(update_fields=["masque_par_membre", "updated_at"])
        record_audit(
            action="loan.hidden_by_member",
            entite_type="Loan",
            entite_id=loan.id,
            user=request.user,
            details={"numero_dossier": loan.numero_dossier},
            ip=client_ip(request),
        )
    return Response({"ok": True, "id": loan.id})


@extend_schema(
    tags=["loans"],
    summary="Demander la reconduction d'un crédit en cours",
    description=(
        "Crée une `LoanRenewal(statut=demandee)` pour le crédit indiqué — "
        "prorogation fixe de **+1 mois** (Article 10). Permission : "
        "`IsActiveMember` (compte membre actif). **Aucun frais** n'est dû : "
        "la reconduction ne fait que **majorer le taux d'intérêt** (Article 11). "
        "La demande passe directement en attente de décision du comité.\n\n"
        "Idempotent : si une renewal `demandee` existe déjà pour ce crédit, "
        "elle est retournée telle quelle (pas de doublon)."
    ),
    request=LoanRenewalRequestSerializer,
    responses={
        201: LoanRenewalReadSerializer,
        400: OpenApiResponse(description="Crédit pas en statut actif/en_retard"),
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

    # CH-4 — Champs ajoutés via FormSchema (loan_renewal) → extra_payload.
    try:
        from apps_coop.forms.services import apply_form_schema

        _RENEWAL_HARDCODED = {
            "nouvelle_duree_mois", "interets_au_comptant", "motif",
        }
        _, extra_payload, schema_version = apply_form_schema(
            "loan_renewal",
            {k: v for k, v in request.data.items()},
            hardcoded_keys=_RENEWAL_HARDCODED,
        )
        if extra_payload or schema_version is not None:
            renewal.extra_payload = extra_payload
            renewal.form_schema_version = schema_version
            renewal.save(update_fields=[
                "extra_payload", "form_schema_version", "updated_at",
            ])
    except Exception:  # noqa: BLE001 — legacy fallback
        import logging
        logging.getLogger(__name__).exception(
            "apply_form_schema('loan_renewal') failed — falling back to legacy",
        )

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

    # Accusé de réception de la demande de reconduction (best-effort).
    if getattr(member.user, "email", None):
        try:
            from django.conf import settings as dj_settings

            from apps_coop.notifications.events import emit_event

            emit_event(
                "loan_renewal.requested",
                member=member,
                context={
                    "prenom": member.prenom,
                    "numero_dossier": loan.numero_dossier,
                    "duree_mois": renewal.nouvelle_duree_mois,
                    "portal_url": getattr(
                        dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"
                    ),
                },
            )
        except Exception:  # noqa: BLE001
            pass

    # Aucun frais : la reconduction n'engendre qu'une majoration de taux.
    # La demande part directement en décision comité.
    payload = LoanRenewalReadSerializer({
        "id": renewal.id,
        "loan_id": loan.id,
        "nouvelle_duree_mois": renewal.nouvelle_duree_mois,
        "statut": renewal.statut,
        "date_demande": renewal.date_demande,
        "frais_reconduction_payment_id": renewal.frais_reconduction_payment_id,
    }).data
    return Response({"renewal": payload}, status=status.HTTP_201_CREATED)


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
        Loan.objects.select_related("member", "member__user", "loan_request")
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

    from apps_coop.common import parse_pagination

    offset, limit = parse_pagination(
        request, default_limit=25, max_limit=_ADMIN_LOANS_PAGE_SIZE
    )
    count = qs.count()
    rows = list(qs[offset : offset + limit])

    # CH-9 — Pré-charge le dernier Payment décaissement pour chaque crédit visible,
    # afin d'éviter N+1 queries quand on calcule disbursement_status par ligne.
    loan_ids = [loan.id for loan in rows]
    last_payment_by_loan: dict[int, Payment] = {}
    if loan_ids:
        for p in (
            Payment.objects.filter(loan_id__in=loan_ids, type=Payment.Type.DECAISSEMENT)
            .order_by("loan_id", "-id")
        ):
            # On garde uniquement le plus récent par crédit (premier rencontré
            # grâce à l'ordre -id).
            last_payment_by_loan.setdefault(p.loan_id, p)

    results = []
    for loan in rows:
        nb_payees = sum(1 for i in loan.installments.all() if i.statut == "payee")
        nb_total = loan.installments.count()
        last_pay = last_payment_by_loan.get(loan.id)
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
            # CH-11 — Affichage net décaissé vs nominal en mode source.
            "mode_retenue_interets": loan.mode_retenue_interets,
            "montant_decaisse_net": (
                str(loan.montant_decaisse_net)
                if loan.montant_decaisse_net is not None else None
            ),
            "interets_retenus_source": (
                str(loan.interets_retenus_source)
                if loan.interets_retenus_source is not None else None
            ),
            # CH-9 — Moyen de réception choisi par le membre (pilote auto-fill payout).
            "moyen_reception": loan.loan_request.moyen_reception or "",
            "recipient_phone": loan.loan_request.recipient_phone or "",
            # CH-9 — Statut du dernier décaissement Payment (pour bouton/badge).
            "disbursement": (
                {
                    "payment_id": last_pay.id,
                    "statut": last_pay.statut,
                    "source": last_pay.source,
                    "reference_externe": last_pay.reference_externe or "",
                }
                if last_pay else None
            ),
        })
    return Response(
        {"count": count, "limit": limit, "offset": offset, "results": results}
    )


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — liste des demandes de reconduction",
    description=(
        "Liste les `LoanRenewal` pour l'espace admin (filtre `?statut=`). "
        "Défaut : toutes. Sert la page admin qui décide les reconductions "
        "demandées par les membres (mobile + portail)."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_loan_renewals(request):
    from .models import LoanRenewal

    qs = (
        LoanRenewal.objects.select_related("loan", "loan__member", "loan__member__user")
        .order_by("-date_demande")
    )
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)

    results = []
    for r in qs[:200]:
        loan = r.loan
        member = loan.member
        results.append({
            "id": r.id,
            "statut": r.statut,
            "statut_display": r.get_statut_display(),
            "loan_id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "numero_membre": member.numero_membre,
            "member_nom": f"{member.prenom} {member.nom}".strip(),
            "montant_credit": str(loan.montant),
            "solde_restant": str(loan.solde_restant),
            "duree_actuelle_mois": loan.duree_mois,
            "nouvelle_duree_mois": r.nouvelle_duree_mois,
            "interets_au_comptant": r.interets_au_comptant,
            "date_demande": r.date_demande.isoformat() if r.date_demande else None,
            "date_decision": r.date_decision.isoformat() if r.date_decision else None,
        })
    return Response({"results": results})


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

    from apps_coop.notifications.events import emit_event

    member = loan.member
    if getattr(member.user, "email", None):
        try:
            emit_event(
                "loan.notice",
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


# ---------------------------------------------------------------------------
# CH-5 — Upload d'un fichier attaché à un LoanRequest (CGA, CFP, CNI, etc.).
# Utilisé après la création du LoanRequest pour persister les fichiers déclarés
# dans le FormSchema actif (champs de type 'file').
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["loans"],
    summary="📎 Upload d'un fichier rattaché à une demande de crédit",
    description=(
        "Multipart upload : `fichier` (binaire) + `schema_field_id` (id du champ "
        "FormSchema source). Crée un Document polymorphe lié au LoanRequest. "
        "Re-upload du même champ remplace le précédent (idempotent par "
        "(loan_request, schema_field_id)). Permission : owner du LoanRequest."
    ),
)
@api_view(["POST"])
@permission_classes([IsActiveMember])
def loan_request_upload_attachment(request, pk: int):
    member = request.user.member
    try:
        lr = LoanRequest.objects.get(pk=pk, member=member)
    except LoanRequest.DoesNotExist:
        return Response(
            {"detail": "Demande de crédit introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    fichier = request.FILES.get("fichier")
    schema_field_id = str(request.data.get("schema_field_id", "")).strip()

    if not fichier:
        return Response(
            {"detail": "Le fichier est requis (champ 'fichier')."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not schema_field_id:
        return Response(
            {"detail": "schema_field_id requis (id du champ FormSchema)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Plafond raisonnable : 10 Mo (le serializer du FormSchema valide aussi
    # max_size_mb côté schéma, mais on garde un garde-fou serveur).
    if fichier.size > 10 * 1024 * 1024:
        return Response(
            {"detail": "Fichier trop volumineux (max 10 Mo)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps_coop.members.models import Document

    # Idempotence : on remplace le précédent upload pour ce même champ.
    Document.objects.filter(
        entite_liee_type="LoanRequest",
        entite_liee_id=lr.id,
        schema_field_id=schema_field_id,
    ).delete()

    doc = Document.objects.create(
        member=member,
        type_doc=Document.TypeDoc.AUTRE,
        entite_liee_type="LoanRequest",
        entite_liee_id=lr.id,
        schema_field_id=schema_field_id,
        fichier=fichier,
        nom_original=(getattr(fichier, "name", "") or "")[:255],
        taille=fichier.size,
    )

    record_audit(
        action="loan_request.attachment_uploaded",
        entite_type="LoanRequest",
        entite_id=lr.id,
        user=request.user,
        details={
            "schema_field_id": schema_field_id,
            "document_id": doc.id,
            "nom_original": doc.nom_original,
            "taille": doc.taille,
        },
        ip=client_ip(request),
    )

    return Response(
        {
            "id": doc.id,
            "schema_field_id": doc.schema_field_id,
            "nom_original": doc.nom_original,
            "taille": doc.taille,
            "url": doc.fichier.url if doc.fichier else None,
        },
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# CH-6 — Double approbation crédit (provisoire → visite terrain → définitive).
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["loans"],
    summary="🔒 Comité — approbation provisoire d'une demande",
    description=(
        "EN_INSTRUCTION → APPROUVEE_PROVISOIRE. Sous réserve d'une visite "
        "terrain favorable, la demande pourra ensuite être approuvée "
        "définitivement via l'endpoint `decide-request`. Permission : "
        "groupe `comite` ou superuser."
    ),
)
@api_view(["POST"])
@permission_classes([IsComite])
def loan_request_decide_provisional(request, pk: int):
    try:
        lr = LoanRequest.objects.get(pk=pk)
    except LoanRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if lr.statut != LoanRequest.Statut.EN_INSTRUCTION:
        return Response(
            {"detail": f"Approbation provisoire impossible depuis le statut {lr.statut!r}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    avis = str(request.data.get("avis_provisoire", "")).strip()
    if not avis:
        return Response(
            {"detail": "Un avis provisoire est requis (champ 'avis_provisoire')."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lr.statut = LoanRequest.Statut.APPROUVEE_PROVISOIRE
    lr.decide_par = request.user
    lr.date_decision = timezone.now()
    # On stocke l'avis provisoire dans avis_instruction si vide ; sinon on
    # concatène pour garder la traçabilité de l'avis d'origine.
    if lr.avis_instruction:
        lr.avis_instruction = f"{lr.avis_instruction}\n\n[Provisoire] {avis}"
    else:
        lr.avis_instruction = f"[Provisoire] {avis}"
    lr.save(update_fields=[
        "statut", "decide_par", "date_decision", "avis_instruction", "updated_at",
    ])

    record_audit(
        action="loan_request.approved_provisional",
        entite_type="LoanRequest",
        entite_id=lr.id,
        user=request.user,
        details={"avis_provisoire": avis},
        ip=client_ip(request),
    )

    from .serializers import LoanRequestReadSerializer as _LRR
    return Response(_LRR(lr).data)


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — enregistrer/valider les frais d'étude (encaissés hors app)",
    description=(
        "Enregistre un règlement des frais d'étude perçu hors application "
        "(ex. espèces à l'agence) pour une demande `en_attente`. Crée un "
        "Payment `frais_demande_credit` MANUEL validé et fait basculer la "
        "demande en `en_instruction` (même effet qu'un paiement Tara). "
        "Body optionnel : `reference`. Permission : loan-requests."
    ),
)
@api_view(["POST"])
@permission_classes([ResourceAccess("loan-requests")])
def loan_request_record_study_fee(request, pk: int):
    import uuid

    from .services import study_fee_for

    try:
        lr = LoanRequest.objects.get(pk=pk)
    except LoanRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if lr.statut != LoanRequest.Statut.EN_ATTENTE:
        return Response(
            {"detail": "Les frais d'étude ne se règlent que sur une demande « en attente (frais à payer) »."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    montant = study_fee_for(getattr(lr, "microcampaign", None))
    payment = Payment.objects.create(
        member=lr.member,
        montant=montant,
        type=Payment.Type.FRAIS_DEMANDE_CREDIT,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        provider_code="",
        reference_externe=str(request.data.get("reference", "")).strip(),
        validated_by=request.user,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
        idempotency_key=uuid.uuid4(),
    )
    # Même effet métier que le webhook Tara : en_attente → en_instruction.
    from apps_coop.payments.services import _hook_loan_request_fees

    _hook_loan_request_fees(payment, {})
    lr.refresh_from_db()
    return Response(LoanRequestReadSerializer(lr).data)


@extend_schema(
    tags=["loans"],
    summary="Membre — régler les frais d'étude par déduction sur son épargne",
    description=(
        "3e canal de règlement des frais d'étude (les deux autres : agence via "
        "`/study-fee/`, mobile money via `/payments/init/`). Prélève le montant "
        "sur l'épargne **classique** du membre et fait basculer la demande "
        "comme n'importe quel encaissement.\n\n"
        "Le prélèvement ne peut mordre que sur la part réellement retirable : "
        "ni le placement ni l'épargne gelée en garantie ne sont ponctionnables. "
        "409 si le disponible est insuffisant ou si la demande n'attend pas de "
        "frais."
    ),
)
@api_view(["POST"])
@permission_classes([IsActiveMember])
def loan_request_pay_study_fee_from_savings(request, pk: int):
    from .study_fee_services import StudyFeeError, pay_study_fee_from_savings

    try:
        lr = LoanRequest.objects.get(pk=pk, member=request.user.member)
    except LoanRequest.DoesNotExist:
        return Response(
            {"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        pay_study_fee_from_savings(lr)
    except StudyFeeError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    lr.refresh_from_db()
    return Response(LoanRequestReadSerializer(lr).data)


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — enregistrer le rapport de visite terrain",
    description=(
        "Enregistre la visite terrain d'une demande APPROUVEE_PROVISOIRE. "
        "Champs requis : `outcome` (favorable|defavorable|a_revoir) + `note`. "
        "Idempotent : ré-enregistre si déjà rempli. Permission : staff."
    ),
)
@api_view(["POST"])
@permission_classes([ResourceAccess("loan-requests")])
def loan_request_field_visit(request, pk: int):
    try:
        lr = LoanRequest.objects.get(pk=pk)
    except LoanRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if lr.statut != LoanRequest.Statut.APPROUVEE_PROVISOIRE:
        return Response(
            {
                "detail": (
                    "La visite terrain ne peut être enregistrée que pour une "
                    "demande approuvée provisoirement."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    outcome = str(request.data.get("outcome", "")).strip()
    note = str(request.data.get("note", "")).strip()
    valid_outcomes = {"favorable", "defavorable", "a_revoir"}
    if outcome not in valid_outcomes:
        return Response(
            {"detail": f"outcome invalide. Valeurs autorisées : {sorted(valid_outcomes)}."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not note:
        return Response(
            {"detail": "Une note de visite est requise (champ 'note')."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lr.field_visit_done_at = timezone.now()
    lr.field_visit_by = request.user
    lr.field_visit_outcome = outcome
    lr.field_visit_note = note
    lr.save(update_fields=[
        "field_visit_done_at", "field_visit_by",
        "field_visit_outcome", "field_visit_note", "updated_at",
    ])

    record_audit(
        action="loan_request.field_visit_recorded",
        entite_type="LoanRequest",
        entite_id=lr.id,
        user=request.user,
        details={"outcome": outcome, "note_length": len(note)},
        ip=client_ip(request),
    )

    # Réponse staff : serializer admin (visite terrain incluse).
    return Response(AdminLoanRequestReadSerializer(lr).data)


# ---------------------------------------------------------------------------
# L4 — Évaluation de la garantie matérielle par la commission (admin).
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — enregistrer l'évaluation du bien (garantie matérielle)",
    description=(
        "Enregistre la valeur du bien évaluée par la commission des prêts sur "
        "une demande en voie GARANTIE MATÉRIELLE. Champ requis : `valeur_estimee` "
        "(≥ 0). `note` optionnelle (concaténée à la description). Purement "
        "informatif : le système n'impose aucune règle de couverture — le "
        "comité juge et approuve via /decide/. Permission : staff."
    ),
)
@api_view(["POST"])
@permission_classes([ResourceAccess("loan-requests")])
def loan_request_evaluate_guarantee(request, pk: int):
    from decimal import Decimal, InvalidOperation

    try:
        lr = LoanRequest.objects.get(pk=pk)
    except LoanRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if not lr.garantie_materielle:
        return Response(
            {"detail": "Cette demande n'est pas en voie garantie matérielle."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw = request.data.get("valeur_estimee")
    try:
        valeur = Decimal(str(raw))
    except (InvalidOperation, TypeError):
        return Response(
            {"detail": "valeur_estimee invalide (nombre attendu)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if valeur < 0:
        return Response(
            {"detail": "valeur_estimee doit être ≥ 0."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    note = str(request.data.get("note", "")).strip()
    fields = ["garantie_valeur_estimee", "updated_at"]
    lr.garantie_valeur_estimee = valeur
    if note:
        prefix = (lr.garantie_description + "\n") if lr.garantie_description else ""
        lr.garantie_description = f"{prefix}[Éval commission] {note}"
        fields.insert(1, "garantie_description")
    lr.save(update_fields=fields)

    record_audit(
        action="loan_request.guarantee_evaluated",
        entite_type="LoanRequest",
        entite_id=lr.id,
        user=request.user,
        details={"valeur_estimee": str(valeur)},
        ip=client_ip(request),
    )

    from .serializers import LoanRequestReadSerializer as _LRR
    return Response(_LRR(lr).data)


# ---------------------------------------------------------------------------
# CH-8 — Extension de la date butoire d'un crédit (admin, avec audit).
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — étendre la date butoire d'un crédit",
    description=(
        "Pose une nouvelle ``date_butoire`` strictement postérieure à l'actuelle. "
        "Le motif est obligatoire (audit). Le crédit doit être actif ou en retard. "
        "Permission : groupe `admin` ou superuser."
    ),
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def loan_extend_deadline(request, pk: int):
    from datetime import date as _date

    try:
        loan = Loan.objects.get(pk=pk)
    except Loan.DoesNotExist:
        return Response({"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if loan.statut not in (Loan.Statut.ACTIF, Loan.Statut.EN_RETARD):
        return Response(
            {
                "detail": (
                    f"Extension impossible : crédit en statut {loan.statut!r}. "
                    "Réservé aux crédits actifs ou en retard."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_date_raw = str(request.data.get("date_butoire", "")).strip()
    motif = str(request.data.get("motif", "")).strip()

    if not new_date_raw:
        return Response(
            {"detail": "Nouvelle date butoire requise (champ 'date_butoire', format YYYY-MM-DD)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not motif:
        return Response(
            {"detail": "Motif requis (champ 'motif')."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        new_date = _date.fromisoformat(new_date_raw)
    except ValueError:
        return Response(
            {"detail": "Format de date invalide. Attendu : YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    current = loan.date_butoire
    if current and new_date <= current:
        return Response(
            {
                "detail": (
                    f"La nouvelle date butoire ({new_date}) doit être strictement "
                    f"postérieure à l'actuelle ({current})."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    loan.date_butoire = new_date
    loan.save(update_fields=["date_butoire", "updated_at"])

    record_audit(
        action="loan.deadline_extended",
        entite_type="Loan",
        entite_id=loan.id,
        user=request.user,
        details={
            "previous": current.isoformat() if current else None,
            "new": new_date.isoformat(),
            "motif": motif,
        },
        ip=client_ip(request),
    )

    return Response(
        {
            "id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "date_butoire": new_date.isoformat(),
            "previous_date_butoire": current.isoformat() if current else None,
            "motif": motif,
        },
    )


# ---------------------------------------------------------------------------
# CH-9 — Note de demande PDF + payout en un clic.
# ---------------------------------------------------------------------------
_MOYEN_TO_NETWORK = {
    "tara_om": "ORANGE",
    "tara_momo": "MTN",
}


@extend_schema(
    tags=["loans"],
    summary="Note de demande de crédit (PDF)",
    description=(
        "Fiche A4 récapitulant la demande : identité, montant, durée, motif, "
        "moyen de réception choisi, et échéancier prévisionnel si la demande "
        "a déjà été approuvée. Accessible au membre demandeur et à l'admin, "
        "à tout moment après création."
    ),
    responses={
        200: OpenApiResponse(description="PDF binaire (application/pdf)"),
        403: OpenApiResponse(description="Pas le propriétaire et pas admin"),
        404: OpenApiResponse(description="Demande introuvable"),
    },
)
@api_view(["GET"])
def loan_request_note(request, pk: int):
    """Télécharge la note PDF d'une `LoanRequest`.

    - Le **membre** demandeur peut télécharger sa propre note.
    - L'**admin** (superuser ou groupe ``coop_admin``) peut télécharger
      n'importe quelle note.

    NB : on n'utilise pas ``IsMember`` car l'admin n'a pas forcément de
    profil membre. La vérification de propriété/admin est faite inline.
    """
    from django.http import HttpResponse

    from .note_pdf import build_loan_request_note

    user = request.user
    if not user.is_authenticated:
        return Response(
            {"detail": "Authentification requise."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        lr = LoanRequest.objects.select_related("member", "loan").get(pk=pk)
    except LoanRequest.DoesNotExist:
        return Response(
            {"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND
        )

    is_admin = user.is_superuser or user.groups.filter(name="coop_admin").exists()
    is_owner = (
        getattr(user, "member", None) is not None
        and lr.member_id == user.member.id
    )
    if not (is_admin or is_owner):
        return Response(
            {"detail": "Vous n'êtes pas autorisé à accéder à cette note."},
            status=status.HTTP_403_FORBIDDEN,
        )

    pdf_bytes = build_loan_request_note(lr)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = f"note-demande-{lr.member.numero_membre}-{lr.id}.pdf"
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — Décaisser maintenant (auto-fill)",
    description=(
        "Bouton « Payer maintenant » côté admin. Lit le `moyen_reception` "
        "saisi par le membre à la soumission, déduit le canal Tara (OM/MTN) "
        "ou le mode espèces, et déclenche le payout sans paramètres "
        "supplémentaires.\n\n"
        "- `tara_om` → payout Tara network=ORANGE\n"
        "- `tara_momo` → payout Tara network=MTN\n"
        "- `agence_especes` → décaissement manuel — `reference_externe` "
        "  doit être fourni dans le body.\n\n"
        "Idempotent : si un Payment décaissement existe déjà (en_attente ou "
        "valide), on le retourne tel quel."
    ),
    responses={
        200: OpenApiResponse(description="Décaissement initié / déjà existant"),
        400: OpenApiResponse(description="Moyen non défini ou ref manuelle manquante"),
        404: OpenApiResponse(description="Crédit introuvable"),
        502: OpenApiResponse(description="Erreur Tara non réessayable"),
        503: OpenApiResponse(description="Tara indisponible (retryable)"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def loan_disburse_now(request, pk: int):
    """Auto-fill du payout depuis ``LoanRequest.moyen_reception``."""
    try:
        loan = Loan.objects.select_related("loan_request").get(pk=pk)
    except Loan.DoesNotExist:
        return Response(
            {"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND
        )

    if loan.statut not in (Loan.Statut.ACTIF, Loan.Statut.EN_RETARD):
        return Response(
            {"detail": f"Crédit en statut {loan.statut!r} — décaissement impossible."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lr = loan.loan_request
    moyen = (lr.moyen_reception or "").strip()
    if not moyen:
        return Response(
            {
                "detail": (
                    "Le membre n'a pas précisé de moyen de réception. "
                    "Utilisez /disburse/ avec mode + paramètres explicites."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if moyen in _MOYEN_TO_NETWORK:
        from .services import tara_payout_enabled

        if not tara_payout_enabled():
            return Response(
                {"detail": "Payout Tara désactivé. Effectuez le virement sur Tara puis enregistrez le décaissement via /disburse/ en mode « manuel » (avec la référence)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        phone = (lr.recipient_phone or "").strip()
        if not phone:
            return Response(
                {"detail": "Numéro Mobile Money manquant sur la demande."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payment = disburse_loan_via_tara(
                loan,
                agent=request.user,
                recipient_phone=phone,
                network=_MOYEN_TO_NETWORK[moyen],
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
        return Response(
            {
                "loan_id": loan.id,
                "numero_dossier": loan.numero_dossier,
                "payment_id": payment.id,
                "mode": "tara",
                "moyen_reception": moyen,
                "statut": payment.statut,
                "reference_externe": payment.reference_externe,
            }
        )

    # Mode manuel — agence_especes : besoin d'une référence externe.
    ref_externe = (request.data.get("reference_externe") or "").strip()
    if not ref_externe:
        return Response(
            {
                "detail": (
                    "Décaissement espèces : reference_externe requise "
                    "(ex. numéro de reçu de caisse)."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    payment = disburse_loan_manual(
        loan,
        agent=request.user,
        reference_externe=ref_externe,
        note=(request.data.get("note") or ""),
    )
    return Response(
        {
            "loan_id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "payment_id": payment.id,
            "mode": "manuel",
            "moyen_reception": moyen,
            "statut": payment.statut,
            "reference_externe": payment.reference_externe,
        }
    )


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — Statut du décaissement",
    description=(
        "Renvoie l'état du dernier `Payment(type=decaissement)` du crédit — "
        "permet à l'admin de monitor un payout Tara en cours sans recharger "
        "toute la page."
    ),
    responses={
        200: OpenApiResponse(description="Statut + détails du Payment"),
        404: OpenApiResponse(description="Crédit introuvable"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdmin])
def loan_disbursement_status(request, pk: int):
    try:
        loan = Loan.objects.get(pk=pk)
    except Loan.DoesNotExist:
        return Response(
            {"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND
        )
    payment = (
        Payment.objects.filter(loan=loan, type=Payment.Type.DECAISSEMENT)
        .order_by("-id")
        .first()
    )
    if not payment:
        return Response(
            {
                "loan_id": loan.id,
                "numero_dossier": loan.numero_dossier,
                "has_payment": False,
            }
        )
    return Response(
        {
            "loan_id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "has_payment": True,
            "payment_id": payment.id,
            "statut": payment.statut,
            "source": payment.source,
            "provider_code": payment.provider_code,
            "reference_externe": payment.reference_externe,
            "motif_rejet": payment.motif_rejet,
            "date_versement": (
                payment.date_versement.isoformat() if payment.date_versement else None
            ),
            "gateway_initiated_at": (
                payment.gateway_initiated_at.isoformat()
                if payment.gateway_initiated_at
                else None
            ),
        }
    )


# ---------------------------------------------------------------------------
# CH-12 — Mes versements prêteur (membre côté épargne placement).
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["loans"],
    summary="Mes versements d'intérêts en tant que prêteur",
    description=(
        "Liste les `LenderInterestPayout` reçus par le membre connecté en tant "
        "que prêteur sur des crédits financés via son épargne classique en "
        "placement (refonte 2026 §7.5 / CH-12). Inclut à la fois les payouts à "
        "T0 (mode source CH-11, `installment=null`) et au fil des remboursements "
        "(mode echeances, LOT 9)."
    ),
    responses={
        200: OpenApiResponse(description="Liste de payouts triés par date desc"),
    },
)
@api_view(["GET"])
@permission_classes([IsMember])
def me_lender_payouts(request):
    from .models import LenderInterestPayout

    member = request.user.member
    qs = (
        LenderInterestPayout.objects.filter(allocation__lender=member)
        .select_related("allocation", "allocation__loan", "installment")
        .order_by("-date", "-id")[:200]
    )
    results = []
    for p in qs:
        loan = p.allocation.loan
        results.append({
            "id": p.id,
            "montant": str(p.montant),
            "date": p.date.isoformat(),
            "loan": {
                "id": loan.id,
                "numero_dossier": loan.numero_dossier,
            },
            "allocation_id": p.allocation_id,
            "quote_part": str(p.allocation.quote_part),
            # CH-12 — installment=None signale un versement à T0 (mode source).
            "kind": "at_source" if p.installment_id is None else "installment",
            "installment_numero": (
                p.installment.numero_echeance if p.installment_id else None
            ),
        })
    return Response({"count": len(results), "results": results})


# ---------------------------------------------------------------------------
# A1 . Admin . Detail credit (echeances + historique remboursement).
#   Endpoint unique, retourne tout le necessaire pour le drawer admin.
#   Marche meme si Loan.statut == cloture (historique conserve).
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — Détail d'un crédit (échéances + remboursements)",
    description=(
        "Pour le drawer admin du détail crédit : renvoie la liste complète des "
        "échéances (`LoanInstallment`) ET l'historique des remboursements "
        "(`LoanRepayment`) pour un crédit donné. Fonctionne aussi pour les "
        "crédits clôturés (l'historique reste disponible)."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_loan_detail(request, pk: int):
    from decimal import Decimal

    from .models import AvalisteConsent, LoanInstallment, LoanRepayment

    try:
        loan = Loan.objects.select_related("member", "loan_request").get(pk=pk)
    except Loan.DoesNotExist:
        return Response({"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND)

    installments = list(
        LoanInstallment.objects.filter(loan=loan).order_by("numero_echeance")
    )
    repayments = list(
        LoanRepayment.objects
        .filter(installment__loan=loan)
        .select_related("payment", "installment")
        .order_by("-date", "-id")
    )

    # --- État complet de l'abonné sur ce crédit (bouton « check » dashboard) ---
    member = loan.member
    lr = loan.loan_request

    # Voie d'obtention (dérivée : la LoanRequest ne stocke pas la route en clair).
    voie = None
    if lr is not None:
        if lr.microcampaign_id:
            voie = "campaign"
        elif lr.garantie_materielle:
            voie = "garantie_materielle"
        elif lr.avaliste_id:
            voie = "avaliste"
        else:
            voie = "senior_brc"

    gel_demandeur = Decimal(getattr(lr, "montant_gele_demandeur", 0) or 0) if lr else Decimal("0")
    montant_demande = Decimal(getattr(lr, "montant_demande", 0) or 0) if lr else Decimal("0")
    sous_couverture = bool(
        lr is not None and voie == "senior_brc" and gel_demandeur < montant_demande
    )

    # Avaliste (garant) + caution engagée.
    avaliste_block = None
    if lr is not None and lr.avaliste_id:
        consent = (
            AvalisteConsent.objects.filter(loan_request=lr)
            .order_by("-id")
            .first()
        )
        av = lr.avaliste
        avaliste_block = {
            "numero_membre": av.numero_membre,
            "nom": av.nom,
            "prenom": av.prenom,
            "caution": str(consent.montant_caution) if consent else None,
        }

    # Garantie matérielle éventuelle.
    garantie_materielle_block = None
    if lr is not None and lr.garantie_materielle:
        garantie_materielle_block = {
            "description": lr.garantie_description or "",
            "valeur_estimee": str(lr.garantie_valeur_estimee or 0),
        }

    # Épargne du membre : collecte + classique (libre / placement / gelé / dispo).
    from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount

    collecte = SavingsAccount.objects.filter(member=member).first()
    classic = ClassicSavingsAccount.objects.filter(member=member).first()
    classic_block = None
    if classic is not None:
        from apps_coop.savings.services import classic_withdrawable

        from .avaliste_services import member_frozen_guarantee

        classic_block = {
            "solde": str(classic.solde),
            "placement_actif": str(classic.solde_placement_actif),
            "gele_credit": str(member_frozen_guarantee(member)),
            "dispo_retrait": str(classic_withdrawable(classic)),
        }

    member_state = {
        "voie": voie,
        "sous_couverture": sous_couverture,
        "gel_demandeur": str(gel_demandeur),
        "montant_demande": str(montant_demande),
        "frais_etude_paye": bool(getattr(lr, "frais_demande_credit_paye", False)) if lr else None,
        "en_attente_decaissement": bool(loan.en_attente_decaissement),
        "issu_reconduction": bool(loan.issu_reconduction),
        "date_butoire": loan.date_butoire.isoformat() if loan.date_butoire else None,
        "montant_decaisse_net": str(loan.montant_decaisse_net),
        "interets_retenus_source": str(loan.interets_retenus_source),
        "avaliste": avaliste_block,
        "garantie_materielle": garantie_materielle_block,
        "epargne": {
            "collecte_solde": str(collecte.solde) if collecte else "0",
            "classique": classic_block,
        },
        "contentieux": {
            "epargne_saisie_montant": str(loan.epargne_saisie_montant or 0),
            "epargne_saisie_at": (
                loan.epargne_saisie_at.isoformat() if loan.epargne_saisie_at else None
            ),
            "poursuite_judiciaire_at": (
                loan.poursuite_judiciaire_at.isoformat()
                if loan.poursuite_judiciaire_at
                else None
            ),
            "penalite_globale_appliquee_at": (
                loan.penalite_globale_appliquee_at.isoformat()
                if loan.penalite_globale_appliquee_at
                else None
            ),
        },
    }

    return Response({
        "member_state": member_state,
        "loan": {
            "id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "montant": str(loan.montant),
            "montant_total_du": str(loan.montant_total_du),
            "solde_restant": str(loan.solde_restant),
            "statut": loan.statut,
            "statut_display": loan.get_statut_display(),
            "date_decaissement": (
                loan.date_decaissement.isoformat() if loan.date_decaissement else None
            ),
            "member": {
                "id": loan.member_id,
                "numero_membre": loan.member.numero_membre,
                "nom": loan.member.nom,
                "prenom": loan.member.prenom,
            },
        },
        "installments": [
            {
                "id": i.id,
                "numero_echeance": i.numero_echeance,
                "date_echeance": i.date_echeance.isoformat(),
                "montant_capital": str(i.montant_capital),
                "montant_interets": str(i.montant_interets),
                "montant_total": str(i.montant_total),
                "montant_paye": str(i.montant_paye),
                "montant_penalite": str(i.montant_penalite),
                "statut": i.statut,
                "statut_display": i.get_statut_display(),
            }
            for i in installments
        ],
        "repayments": [
            {
                "id": r.id,
                "installment_numero": r.installment.numero_echeance,
                "installment_id": r.installment_id,
                "payment_id": r.payment_id,
                "payment_type": r.payment.type,
                "payment_source": r.payment.source,
                "payment_reference_externe": r.payment.reference_externe or "",
                "montant_impute": str(r.montant_impute),
                "date": r.date.isoformat(),
            }
            for r in repayments
        ],
        "totaux": {
            "rembourse_total": str(
                sum((r.montant_impute for r in repayments), start=__import__("decimal").Decimal("0"))
            ),
            "nb_repayments": len(repayments),
            "nb_installments_payees": sum(
                1 for i in installments if i.statut == "payee"
            ),
            "nb_installments_total": len(installments),
        },
    })


# ---------------------------------------------------------------------------
# A2 . Admin . Liste des echeances filtrables.
#   Sert au widget "Suivi paiement" du dashboard (echeances a venir + en retard).
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — Liste des échéances filtrables (suivi paiement)",
    description=(
        "Liste paginee de `LoanInstallment` pour le widget Suivi paiement. "
        "Filtres : `?statut=a_venir|en_retard|partielle|payee` (CSV accepte), "
        "`?member=<id>`, `?loan=<id>`, `?from=YYYY-MM-DD&to=YYYY-MM-DD` sur "
        "`date_echeance`. Par defaut : non-payees (a_venir + en_retard + "
        "partielle), tri date_echeance ASC."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_installments(request):
    from .models import LoanInstallment

    qs = (
        LoanInstallment.objects
        .select_related("loan", "loan__member")
        .order_by("date_echeance", "loan_id", "numero_echeance")
    )

    statut_param = (request.query_params.get("statut") or "").strip()
    if statut_param:
        wanted = [s.strip() for s in statut_param.split(",") if s.strip()]
        qs = qs.filter(statut__in=wanted)
    else:
        # Defaut : echeances non encore soldees (utile pour "Remboursements en
        # attente" du dashboard).
        qs = qs.exclude(statut=LoanInstallment.Statut.PAYEE)

    member_id = request.query_params.get("member")
    if member_id:
        qs = qs.filter(loan__member_id=member_id)
    loan_id = request.query_params.get("loan")
    if loan_id:
        qs = qs.filter(loan_id=loan_id)
    date_from = request.query_params.get("from")
    if date_from:
        qs = qs.filter(date_echeance__gte=date_from)
    date_to = request.query_params.get("to")
    if date_to:
        qs = qs.filter(date_echeance__lte=date_to)

    from apps_coop.common import parse_pagination

    offset, limit = parse_pagination(request, default_limit=25, max_limit=200)
    count = qs.count()
    rows = list(qs[offset : offset + limit])

    results = []
    for i in rows:
        loan = i.loan
        results.append({
            "id": i.id,
            "numero_echeance": i.numero_echeance,
            "date_echeance": i.date_echeance.isoformat(),
            "montant_total": str(i.montant_total),
            "montant_paye": str(i.montant_paye),
            "montant_penalite": str(i.montant_penalite),
            "montant_restant": str(
                max(
                    __import__("decimal").Decimal(i.montant_total)
                    + __import__("decimal").Decimal(i.montant_penalite)
                    - __import__("decimal").Decimal(i.montant_paye),
                    __import__("decimal").Decimal("0"),
                )
            ),
            "statut": i.statut,
            "statut_display": i.get_statut_display(),
            "loan": {
                "id": loan.id,
                "numero_dossier": loan.numero_dossier,
            },
            "member": {
                "id": loan.member_id,
                "numero_membre": loan.member.numero_membre,
                "nom": loan.member.nom,
                "prenom": loan.member.prenom,
            },
        })
    return Response(
        {"count": count, "limit": limit, "offset": offset, "results": results}
    )
