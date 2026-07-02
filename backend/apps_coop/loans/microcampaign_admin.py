"""Admin endpoints pour MicrocreditCampaign (refonte 2026 — LOT 16).

Liste/crée/clôture les campagnes micro-crédit (voie 3 d'éligibilité §8).
Permet aussi au comité de valider ou rejeter les LoanRequest en statut
``EN_VALIDATION_CAMPAGNE`` (étape intermédiaire entre la soumission par
le membre TEMPORAIRE et l'instruction standard).

Endpoints exposés (montés dans ``urls.py``) :
  GET    /loans/admin/campaigns/            — liste paginée + filtres
  POST   /loans/admin/campaigns/            — créer une campagne
  GET    /loans/admin/campaigns/<id>/       — détail + bénéficiaires
  PATCH  /loans/admin/campaigns/<id>/close/ — clôture manuelle (idempotent)
  POST   /loans/admin/requests/<id>/campaign-decide/ — valide/rejette LR
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import record as record_audit
from apps_coop.members.permissions import IsComite, IsStaff

from .microcampaign_services import close_campaign
from .models import LoanRequest, MicrocreditCampaign

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


class MicrocampaignCreateSerializer(serializers.Serializer):
    """Body de ``POST /loans/admin/campaigns/``.

    Accepte multipart/form-data si un ``flyer`` est joint (sinon JSON marche
    parfaitement). DRF gère les deux via les parsers globaux.
    """

    nom = serializers.CharField(max_length=120)
    profil_cible = serializers.CharField(max_length=64)
    date_debut = serializers.DateField()
    date_fin = serializers.DateField()
    montant_min = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, default=Decimal("0")
    )
    montant_max = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("100")
    )
    taux_interet = serializers.DecimalField(
        max_digits=5, decimal_places=4, min_value=0, max_value=1
    )
    nb_jours_recouvrement = serializers.IntegerField(min_value=1, max_value=365)
    plafond_beneficiaires = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=10000
    )
    # Config onboarding 2026.
    membre_requis = serializers.BooleanField(required=False, default=True)
    frais_etude_montant = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0,
        required=False, allow_null=True,
        help_text="Frais d'étude (FCFA). Vide = tarif standard ; 0 = gratuit.",
    )
    flyer = serializers.ImageField(
        required=False, allow_null=True,
        help_text="Visuel facultatif joint à la campagne (PNG/JPG).",
    )

    def validate(self, attrs):
        if attrs["date_fin"] < attrs["date_debut"]:
            raise serializers.ValidationError(
                {"date_fin": "Doit être ≥ date_debut."}
            )
        if attrs["montant_max"] < attrs["montant_min"]:
            raise serializers.ValidationError(
                {"montant_max": "Doit être ≥ montant_min."}
            )
        return attrs


class MicrocampaignCloseSerializer(serializers.Serializer):
    """Body de ``PATCH /loans/admin/campaigns/<id>/close/``."""

    reason = serializers.CharField(max_length=64, required=False, allow_blank=True)


class LoanRequestCampaignDecisionSerializer(serializers.Serializer):
    """Body de ``POST /loans/admin/requests/<id>/campaign-decide/``."""

    decision = serializers.ChoiceField(choices=["valide", "rejete"])
    motif_rejet = serializers.CharField(
        max_length=2000, required=False, allow_blank=True
    )

    def validate(self, attrs):
        if attrs["decision"] == "rejete" and not (attrs.get("motif_rejet") or "").strip():
            raise serializers.ValidationError(
                {"motif_rejet": "Requis pour rejeter une demande micro-crédit."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Helpers de sérialisation
# ---------------------------------------------------------------------------


def _flyer_url(c: MicrocreditCampaign, request=None) -> str | None:
    """URL **relative** du flyer (ou None si absent).

    NB : on renvoie volontairement le chemin relatif `/media/...`. Le front
    (admin :3202) proxifie /media/* vers le backend interne — c'est ce qui
    permet d'afficher le flyer dans <img> ou <iframe>. Renvoyer une absolute
    URL ici embarquerait l'host interne `backend:8000` (non résoluble côté
    navigateur).
    """
    try:
        return c.flyer.url if c.flyer else None
    except (ValueError, AttributeError):
        return None


def _row(
    c: MicrocreditCampaign,
    *,
    nb_loans: int | None = None,
    request=None,
) -> dict:
    today = timezone.localdate()
    is_open = bool(c.actif) and c.date_debut <= today <= c.date_fin
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
        "plafond_beneficiaires": c.plafond_beneficiaires,
        "membre_requis": c.membre_requis,
        "frais_etude_montant": (
            str(c.frais_etude_montant) if c.frais_etude_montant is not None else None
        ),
        "actif": c.actif,
        "is_open": is_open,
        "closed_at": c.closed_at.isoformat() if c.closed_at else None,
        "close_reason": c.close_reason or "",
        "beneficiaires_count": nb_loans if nb_loans is not None else c.beneficiaires.count(),
        "targeted_count": c.targeted_members.count(),
        "flyer_url": _flyer_url(c, request),
        "created_at": c.created_at.isoformat(),
        "created_by_id": c.created_by_id,
    }


# ---------------------------------------------------------------------------
# GET / POST /loans/admin/campaigns/
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — liste des campagnes micro-crédit (refonte 2026 §8)",
    description=(
        "Renvoie la liste des campagnes. Filtres optionnels : "
        "`?actif=true|false`, `?profil_cible=<str>`, `?is_open=true` (actif + dans la fenêtre)."
    ),
    responses={200: OpenApiResponse(description="`{ count, results: Campaign[] }`")},
)
@extend_schema(
    methods=["POST"],
    tags=["loans"],
    summary="🔒 Staff — créer une campagne micro-crédit",
    description="Pose `created_by=request.user`. Audit `microcampaign.created`.",
    request=MicrocampaignCreateSerializer,
    responses={201: OpenApiResponse(description="Campagne créée"), 400: OpenApiResponse(description="Validation")},
)
@api_view(["GET", "POST"])
@permission_classes([IsStaff])
def admin_campaigns(request):
    if request.method == "GET":
        return _list_campaigns(request)
    return _create_campaign(request)


def _list_campaigns(request):
    qs = MicrocreditCampaign.objects.annotate(
        nb_loans=Count("beneficiaires", distinct=True)
    ).order_by("-date_debut", "-id")

    # Soft-delete : exclu par defaut, sauf si l'admin demande explicitement
    # ?include_deleted=true pour la vue archives.
    include_deleted = (request.query_params.get("include_deleted") or "").lower()
    if include_deleted not in ("true", "1", "yes"):
        qs = qs.filter(deleted_at__isnull=True)

    actif = (request.query_params.get("actif") or "").lower()
    if actif in ("true", "1", "yes"):
        qs = qs.filter(actif=True)
    elif actif in ("false", "0", "no"):
        qs = qs.filter(actif=False)

    profil = (request.query_params.get("profil_cible") or "").strip()
    if profil:
        qs = qs.filter(profil_cible__iexact=profil)

    is_open = (request.query_params.get("is_open") or "").lower()
    if is_open in ("true", "1", "yes"):
        today = timezone.localdate()
        qs = qs.filter(actif=True, date_debut__lte=today, date_fin__gte=today)

    count = qs.count()
    rows = [_row(c, nb_loans=c.nb_loans, request=request) for c in qs[:200]]
    return Response({"count": count, "results": rows})


@transaction.atomic
def _create_campaign(request):
    s = MicrocampaignCreateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    c = MicrocreditCampaign.objects.create(
        nom=data["nom"].strip(),
        profil_cible=data["profil_cible"].strip(),
        date_debut=data["date_debut"],
        date_fin=data["date_fin"],
        montant_min=data["montant_min"],
        montant_max=data["montant_max"],
        taux_interet=data["taux_interet"],
        nb_jours_recouvrement=data["nb_jours_recouvrement"],
        plafond_beneficiaires=data.get("plafond_beneficiaires"),
        membre_requis=data.get("membre_requis", True),
        frais_etude_montant=data.get("frais_etude_montant"),
        actif=True,
        created_by=request.user,
    )
    # Flyer joint (optionnel)
    flyer = data.get("flyer")
    if flyer:
        c.flyer = flyer
        c.save(update_fields=["flyer", "updated_at"])

    record_audit(
        action="microcampaign.created",
        entite_type="MicrocreditCampaign",
        entite_id=c.id,
        details={
            "nom": c.nom,
            "profil_cible": c.profil_cible,
            "date_debut": c.date_debut.isoformat(),
            "date_fin": c.date_fin.isoformat(),
            "montant_max": str(c.montant_max),
            "plafond_beneficiaires": c.plafond_beneficiaires,
            "has_flyer": bool(flyer),
        },
    )

    # Broadcast notification a tous les membres ACTIF . email + in-app.
    # Best-effort : la creation reussit meme si la diffusion echoue.
    _broadcast_campaign_to_actives(c)

    return Response(_row(c, request=request), status=status.HTTP_201_CREATED)


def _broadcast_campaign_to_actives(campaign):
    """Notifie tous les membres ACTIF d'une nouvelle campagne micro-credit.

    Cree une Notification in-app par membre + envoie un email transactionnel
    (template campaign.created). Loggue silencieusement les echecs.
    """
    from apps_coop.members.models import Member
    from apps_coop.notifications.events import emit_event
    from apps_coop.notifications.models import Notification

    members = Member.objects.filter(statut=Member.Statut.ACTIF).select_related("user")
    sent_inapp = sent_email = 0
    titre = f"Nouvelle campagne : {campaign.nom}"
    corps = (
        f"La cooperative ouvre une nouvelle campagne micro-credit ciblee "
        f"{campaign.profil_cible}. Plafond : {campaign.montant_max} XAF. "
        f"Du {campaign.date_debut} au {campaign.date_fin}."
    )
    payload = {
        "campaign_id": campaign.id,
        "deeplink": f"/credit/campagnes/{campaign.id}",
    }
    for m in members:
        # In-app . idempotent : on ne re-cree pas si deja diffusee
        try:
            Notification.objects.get_or_create(
                member=m,
                kind=getattr(Notification.Kind, "ANNOUNCEMENT", "announcement"),
                titre=titre,
                defaults={"corps": corps, "payload": payload},
            )
            sent_inapp += 1
        except Exception:  # noqa: BLE001
            logger.warning("Notification in-app campagne #%s skipped for member #%s",
                           campaign.id, m.id, exc_info=True)
        # Email transactionnel
        if m.user and m.user.email:
            try:
                emit_event(
                    "campaign.created",
                    to_email=m.user.email,
                    member=m,
                    context={
                        "prenom": m.prenom or "",
                        "nom": m.nom or "",
                        "nom_campagne": campaign.nom,
                        "profil_cible": campaign.profil_cible,
                        "montant_min": str(campaign.montant_min),
                        "montant_max": str(campaign.montant_max),
                        "date_debut": str(campaign.date_debut),
                        "date_fin": str(campaign.date_fin),
                        "taux_interet": str(campaign.taux_interet),
                    },
                )
                sent_email += 1
            except Exception:  # noqa: BLE001
                logger.warning("Email campagne #%s skipped for %s",
                               campaign.id, m.user.email, exc_info=True)
    logger.info("Campaign #%s broadcast : in-app=%s email=%s",
                campaign.id, sent_inapp, sent_email)


# ---------------------------------------------------------------------------
# GET /loans/admin/campaigns/<id>/ — détail + bénéficiaires + LR en attente
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — détail d'une campagne (avec bénéficiaires et LR en attente)",
    responses={200: OpenApiResponse(description="Détail campagne enrichi")},
)
@api_view(["GET", "DELETE"])
@permission_classes([IsStaff])
def admin_campaign_detail(request, pk: int):
    try:
        c = MicrocreditCampaign.objects.get(pk=pk)
    except MicrocreditCampaign.DoesNotExist:
        return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)

    # Soft-delete admin . la campagne est masquee mais les LoanRequest qui
    # la referencent restent intactes (FK on_delete=PROTECT cote modele).
    if request.method == "DELETE":
        if c.deleted_at is not None:
            return Response({"detail": "Campagne deja supprimee."}, status=status.HTTP_400_BAD_REQUEST)
        c.deleted_at = timezone.now()
        c.actif = False  # masquee = plus de nouvelles demandes
        c.save(update_fields=["deleted_at", "actif", "updated_at"])
        record_audit(
            action="microcampaign.soft_deleted",
            entite_type="MicrocreditCampaign",
            entite_id=c.id,
            details={"nom": c.nom, "by_user": request.user.id if request.user else None},
        )
        return Response(
            {"id": c.id, "deleted_at": c.deleted_at.isoformat(), "detail": "Campagne archivee."},
            status=status.HTTP_200_OK,
        )

    pending = LoanRequest.objects.filter(
        microcampaign=c,
        statut=LoanRequest.Statut.EN_VALIDATION_CAMPAGNE,
    ).select_related("member").order_by("date_soumission")

    pending_rows = [
        {
            "id": lr.id,
            "member_id": lr.member_id,
            "member_nom": f"{lr.member.prenom} {lr.member.nom}".strip(),
            "member_numero": lr.member.numero_membre,
            "montant_demande": str(lr.montant_demande),
            "duree_mois": lr.duree_mois,
            "motif": lr.motif,
            "date_soumission": lr.date_soumission.isoformat(),
        }
        for lr in pending
    ]

    # Bénéficiaires — membres TEMPORAIRE/ADHERENT créés via la campagne,
    # enrichis avec leur crédit issu de la campagne (souscription + état du
    # remboursement) pour un vrai suivi côté admin.
    from .models import Loan

    beneficiaires = c.beneficiaires.select_related("user").order_by("date_adhesion")
    benef_rows = []
    for m in beneficiaires:
        # Loan créé via une LoanRequest de cette campagne. On prend le plus
        # récent — en pratique 1 seul par membre tant que pas remboursé.
        loan = (
            Loan.objects.filter(
                member=m,
                loan_request__microcampaign=c,
            )
            .order_by("-date_decaissement", "-id")
            .first()
        )
        loan_info = None
        if loan is not None:
            montant = float(loan.montant or 0)
            solde = float(loan.solde_restant or 0)
            pct = round((montant - solde) / montant * 100, 1) if montant > 0 else 0
            loan_info = {
                "id": loan.id,
                "numero_dossier": loan.numero_dossier,
                "montant": str(loan.montant),
                "solde_restant": str(loan.solde_restant),
                "statut": loan.statut,
                "statut_display": loan.get_statut_display(),
                "date_decaissement": loan.date_decaissement.isoformat()
                if loan.date_decaissement
                else None,
                "pct_rembourse": pct,
            }
        benef_rows.append(
            {
                "id": m.id,
                "numero_membre": m.numero_membre,
                "nom": m.nom,
                "prenom": m.prenom,
                "statut": m.statut,
                "date_adhesion": m.date_adhesion.isoformat(),
                "loan": loan_info,
            }
        )

    # Audience — membres explicitement ciblés (M2M, peuvent être différents
    # des bénéficiaires, qui ne se matérialisent qu'après acceptation du LR).
    targeted = c.targeted_members.select_related("user").order_by("nom", "prenom")
    targeted_rows = [
        {
            "id": m.id,
            "numero_membre": m.numero_membre,
            "nom": m.nom,
            "prenom": m.prenom,
            "statut": m.statut,
        }
        for m in targeted
    ]

    body = _row(c, nb_loans=len(benef_rows), request=request)
    body["pending_requests"] = pending_rows
    body["pending_count"] = len(pending_rows)
    body["beneficiaires"] = benef_rows
    body["targeted_members"] = targeted_rows
    return Response(body)


# ---------------------------------------------------------------------------
# PATCH /loans/admin/campaigns/<id>/close/ — clôture manuelle
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — clôture manuelle d'une campagne",
    description=(
        "Pose `actif=False` + `closed_at` + `close_reason` (optionnel). Idempotent : "
        "rappeler sur une campagne déjà fermée ne change rien."
    ),
    request=MicrocampaignCloseSerializer,
    responses={200: OpenApiResponse(description="Campagne fermée")},
)
@api_view(["PATCH"])
@permission_classes([IsStaff])
def admin_campaign_close(request, pk: int):
    try:
        c = MicrocreditCampaign.objects.get(pk=pk)
    except MicrocreditCampaign.DoesNotExist:
        return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)

    s = MicrocampaignCloseSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    reason = (s.validated_data.get("reason") or "manual").strip() or "manual"

    c = close_campaign(c, reason=reason)
    return Response(_row(c, request=request))


# ---------------------------------------------------------------------------
# POST /loans/admin/requests/<id>/campaign-decide/ — comité valide/rejette
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Comité — valide ou rejette une LR micro-crédit (EN_VALIDATION_CAMPAGNE)",
    description=(
        "La LR doit être en statut `en_validation_campagne`. Deux issues :\n\n"
        "- `decision=valide` → passe `statut=en_instruction` (parcours standard reprend).\n"
        "- `decision=rejete` → pose `statut=rejetee_campagne` + `motif_rejet` (terminal).\n\n"
        "Audit `microcampaign.lr_validated` / `microcampaign.lr_rejected`."
    ),
    request=LoanRequestCampaignDecisionSerializer,
    responses={
        200: OpenApiResponse(description="Décision enregistrée"),
        400: OpenApiResponse(description="Statut incompatible"),
        404: OpenApiResponse(description="Demande introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsComite])
@transaction.atomic
def admin_loan_request_campaign_decide(request, pk: int):
    try:
        # ``microcampaign`` est nullable → LEFT OUTER JOIN incompatible avec un
        # FOR UPDATE global. ``of=("self",)`` ne verrouille que la ligne
        # LoanRequest, les jointures restent en SELECT simple.
        lr = LoanRequest.objects.select_for_update(of=("self",)).select_related(
            "member", "microcampaign"
        ).get(pk=pk)
    except LoanRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if lr.statut != LoanRequest.Statut.EN_VALIDATION_CAMPAGNE:
        return Response(
            {"detail": f"Demande pas en validation campagne (statut={lr.statut})."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    s = LoanRequestCampaignDecisionSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    if data["decision"] == "valide":
        lr.statut = LoanRequest.Statut.EN_INSTRUCTION
        lr.save(update_fields=["statut", "updated_at"])
        record_audit(
            action="microcampaign.lr_validated",
            entite_type="LoanRequest",
            entite_id=lr.id,
            details={
                "campaign_id": lr.microcampaign_id,
                "validated_by": request.user.id,
            },
        )
        return Response(
            {
                "id": lr.id,
                "statut": lr.statut,
                "campaign_id": lr.microcampaign_id,
                "message": "Demande validée — passe en instruction standard.",
            }
        )

    # rejet
    motif = s.validated_data["motif_rejet"].strip()
    lr.statut = LoanRequest.Statut.REJETEE_CAMPAGNE
    lr.motif_rejet = motif
    lr.date_decision = timezone.now()
    lr.decide_par = request.user
    lr.save(update_fields=[
        "statut", "motif_rejet", "date_decision", "decide_par", "updated_at",
    ])
    record_audit(
        action="microcampaign.lr_rejected",
        entite_type="LoanRequest",
        entite_id=lr.id,
        details={
            "campaign_id": lr.microcampaign_id,
            "rejected_by": request.user.id,
            "motif": motif,
        },
    )
    return Response(
        {
            "id": lr.id,
            "statut": lr.statut,
            "campaign_id": lr.microcampaign_id,
            "motif_rejet": motif,
            "message": "Demande rejetée (terminal).",
        }
    )


# ---------------------------------------------------------------------------
# POST/DELETE /loans/admin/campaigns/<id>/targeted/ — audience (M2M)
# ---------------------------------------------------------------------------


class TargetedAddSerializer(serializers.Serializer):
    """Body de ``POST /loans/admin/campaigns/<id>/targeted/``.

    Accepte une liste de ``member_ids`` OU une liste de ``numeros_membre``
    (mix toléré). Les inconnus sont remontés dans ``not_found`` plutôt que
    de rejeter toute la requête.
    """

    member_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False, allow_empty=True, default=list,
    )
    numeros_membre = serializers.ListField(
        child=serializers.CharField(max_length=32),
        required=False, allow_empty=True, default=list,
    )

    def validate(self, attrs):
        if not (attrs.get("member_ids") or attrs.get("numeros_membre")):
            raise serializers.ValidationError(
                "Fournis au moins un member_ids ou numeros_membre."
            )
        return attrs


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — ajoute des membres ciblés à une campagne",
    description=(
        "Pose la relation M2M `targeted_members`. Idempotent (les doublons "
        "sont ignorés silencieusement). Renvoie le détail à jour + la liste "
        "des numéros/IDs introuvables (`not_found`)."
    ),
    request=TargetedAddSerializer,
    responses={
        200: OpenApiResponse(description="Membres ajoutés (audience à jour)"),
        404: OpenApiResponse(description="Campagne introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsStaff])
@transaction.atomic
def admin_campaign_targeted_add(request, pk: int):
    from apps_coop.members.models import Member

    try:
        c = MicrocreditCampaign.objects.get(pk=pk)
    except MicrocreditCampaign.DoesNotExist:
        return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)

    s = TargetedAddSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    member_ids = set(data.get("member_ids") or [])
    numeros = [n.strip() for n in (data.get("numeros_membre") or []) if n and n.strip()]

    found = list(Member.objects.filter(pk__in=member_ids))
    if numeros:
        found += list(Member.objects.filter(numero_membre__in=numeros).exclude(pk__in=[m.pk for m in found]))

    found_ids = {m.pk for m in found}
    found_numeros = {m.numero_membre for m in found}
    not_found = {
        "member_ids": sorted(member_ids - found_ids),
        "numeros_membre": sorted(set(numeros) - found_numeros),
    }

    if found:
        c.targeted_members.add(*found)
        record_audit(
            action="microcampaign.targeted_added",
            entite_type="MicrocreditCampaign",
            entite_id=c.id,
            user=request.user,
            details={
                "added_member_ids": [m.pk for m in found],
                "added_numeros": [m.numero_membre for m in found],
                "not_found": not_found,
            },
        )

    return Response(
        {
            "campaign": _row(c, request=request),
            "added_count": len(found),
            "not_found": not_found,
            "targeted_members": [
                {
                    "id": m.id,
                    "numero_membre": m.numero_membre,
                    "nom": m.nom,
                    "prenom": m.prenom,
                    "statut": m.statut,
                }
                for m in c.targeted_members.select_related("user").order_by("nom", "prenom")
            ],
        }
    )


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — retire un membre ciblé d'une campagne",
    description="Idempotent : retirer un membre non présent ne lève pas d'erreur.",
    responses={
        200: OpenApiResponse(description="Membre retiré"),
        404: OpenApiResponse(description="Campagne ou membre introuvable"),
    },
)
@api_view(["DELETE"])
@permission_classes([IsStaff])
@transaction.atomic
def admin_campaign_targeted_remove(request, pk: int, member_id: int):
    from apps_coop.members.models import Member

    try:
        c = MicrocreditCampaign.objects.get(pk=pk)
    except MicrocreditCampaign.DoesNotExist:
        return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)
    try:
        m = Member.objects.get(pk=member_id)
    except Member.DoesNotExist:
        return Response({"detail": "Membre introuvable."}, status=status.HTTP_404_NOT_FOUND)

    was_targeted = c.targeted_members.filter(pk=m.pk).exists()
    c.targeted_members.remove(m)
    if was_targeted:
        record_audit(
            action="microcampaign.targeted_removed",
            entite_type="MicrocreditCampaign",
            entite_id=c.id,
            user=request.user,
            details={"removed_member_id": m.id, "numero": m.numero_membre},
        )
    return Response({"removed": was_targeted, "targeted_count": c.targeted_members.count()})


# ---------------------------------------------------------------------------
# Candidatures visiteurs (non-membres) — liste + décision (onboarding 2026)
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans-admin"],
    summary="🔒 Comité — liste des candidatures visiteurs d'une campagne",
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_campaign_applications(request, pk: int):
    from .models import CampaignApplication

    try:
        c = MicrocreditCampaign.objects.get(pk=pk)
    except MicrocreditCampaign.DoesNotExist:
        return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)
    statut = request.query_params.get("statut")
    qs = c.applications.all().order_by("-created_at")
    if statut:
        qs = qs.filter(statut=statut)
    rows = [
        {
            "id": a.id,
            "nom": a.nom,
            "prenom": a.prenom,
            "phone": a.phone,
            "email": a.email,
            "montant_demande": str(a.montant_demande),
            "motif": a.motif,
            "statut": a.statut,
            "statut_display": a.get_statut_display(),
            "created_at": a.created_at.isoformat(),
            "member_id": a.member_id,
            "numero_membre": a.member.numero_membre if a.member_id else None,
            "loan_request_id": a.loan_request_id,
        }
        for a in qs[:300]
    ]
    return Response({"count": len(rows), "results": rows})


@extend_schema(
    tags=["loans-admin"],
    summary="🔒 Comité — accepter/rejeter une candidature visiteur",
    description=(
        "`decision=accepte` → crée le compte bénéficiaire (statut actif, SANS "
        "frais d'adhésion), envoie le mail de mot de passe et ouvre un "
        "LoanRequest en instruction. `decision=rejete` → aucun compte créé."
    ),
)
@api_view(["POST"])
@permission_classes([IsComite])
def admin_campaign_application_decide(request, pk: int):
    from .microcampaign_services import (
        accept_campaign_application,
        reject_campaign_application,
    )
    from .models import CampaignApplication

    try:
        app = CampaignApplication.objects.select_for_update(of=("self",)).get(pk=pk)
    except CampaignApplication.DoesNotExist:
        return Response({"detail": "Candidature introuvable."}, status=status.HTTP_404_NOT_FOUND)

    decision = (request.data.get("decision") or "").strip()
    try:
        if decision == "accepte":
            app = accept_campaign_application(app, decided_by=request.user)
            return Response(
                {
                    "id": app.id,
                    "statut": app.statut,
                    "member_id": app.member_id,
                    "loan_request_id": app.loan_request_id,
                    "message": "Candidature acceptée — compte créé, mail de mot de passe envoyé.",
                }
            )
        if decision == "rejete":
            app = reject_campaign_application(
                app, decided_by=request.user,
                motif_rejet=request.data.get("motif_rejet", ""),
            )
            return Response({"id": app.id, "statut": app.statut})
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {"detail": "decision doit être 'accepte' ou 'rejete'."},
        status=status.HTTP_400_BAD_REQUEST,
    )
