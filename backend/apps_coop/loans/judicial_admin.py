"""Admin endpoints pour JudicialEscalation (refonte 2026 — LOT 17).

Pilote les phases D/E du contentieux : huissier → décision → exécution.
Tous les services métier vivent dans ``judicial_services.py``. Ce module
n'expose que la couche HTTP + validation des bodies.

Endpoints exposés (montés dans ``urls.py``) :
  GET    /loans/admin/escalations/                — liste paginée + filtres
  GET    /loans/admin/escalations/<id>/           — détail enrichi
  POST   /loans/admin/loans/<loan_id>/escalation/ — ouverture (phase D)
  POST   /loans/admin/escalations/<id>/decision/  — phase E1 — décision rendue
  POST   /loans/admin/escalations/<id>/execution/ — phase E2 — biens saisis
  POST   /loans/admin/escalations/<id>/classer/   — abandon (CLASSEE_SANS_SUITE)
"""
from __future__ import annotations


from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.naming import full_name
from apps_coop.members.permissions import IsAdmin, IsStaff

from .judicial_services import (
    classer_sans_suite,
    open_judicial_escalation,
    record_judicial_decision,
    record_judicial_execution,
)
from .models import JudicialEscalation, Loan


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


class JudicialOpenSerializer(serializers.Serializer):
    motif = serializers.CharField(max_length=4000, allow_blank=False)
    mode = serializers.ChoiceField(
        choices=["manual", "auto", "hybrid"], default="manual"
    )


class BienItemSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=200, allow_blank=False)
    valeur_estimee = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )


class JudicialDecisionSerializer(serializers.Serializer):
    decision_date = serializers.DateField()
    biens_saisissables = serializers.ListField(
        child=BienItemSerializer(), required=False, allow_empty=True, default=list
    )


class JudicialExecutionSerializer(serializers.Serializer):
    execution_date = serializers.DateField()
    montant_recouvre = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0
    )
    biens_saisis = serializers.ListField(
        child=BienItemSerializer(), required=False, allow_empty=True, default=list
    )


class JudicialClasserSerializer(serializers.Serializer):
    motif = serializers.CharField(max_length=4000, allow_blank=False)


# ---------------------------------------------------------------------------
# Sérialisation read-side
# ---------------------------------------------------------------------------


def _row(e: JudicialEscalation, *, loan: Loan | None = None) -> dict:
    loan = loan or e.loan
    return {
        "id": e.id,
        "loan_id": e.loan_id,
        "loan_numero_dossier": loan.numero_dossier,
        "member_id": loan.member_id,
        "member_numero": loan.member.numero_membre,
        "member_nom": full_name(loan.member.prenom, loan.member.nom),
        "statut": e.statut,
        "statut_display": e.get_statut_display(),
        "declenche_at": e.declenche_at.isoformat(),
        "declenche_par_id": e.declenche_par_id,
        "declenche_mode": e.declenche_mode,
        "motif": e.motif,
        "documents_attaches": list(e.documents_attaches or []),
        "decision_date": e.decision_date.isoformat() if e.decision_date else None,
        "biens_saisissables": list(e.biens_saisissables or []),
        "execution_date": e.execution_date.isoformat() if e.execution_date else None,
        "montant_recouvre": str(e.montant_recouvre),
        "biens_saisis": list(e.biens_saisis or []),
        "closed_at": e.closed_at.isoformat() if e.closed_at else None,
        "close_reason": e.close_reason or "",
        "loan_solde_restant": str(loan.solde_restant),
        "loan_statut": loan.statut,
    }


# ---------------------------------------------------------------------------
# GET /loans/admin/escalations/ — liste paginée + filtres
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — liste des escalades judiciaires (refonte 2026 §9.3-9.4)",
    description=(
        "Filtres optionnels : `?statut=en_instance|decision_rendue|executee|classee_sans_suite`, "
        "`?open=true` (raccourci pour statut ∈ {en_instance, decision_rendue}), "
        "`?member=<id>`, `?q=<numero_dossier|nom>`."
    ),
    responses={200: OpenApiResponse(description="`{ count, results: Escalation[] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_escalations(request):
    qs = (
        JudicialEscalation.objects.select_related("loan", "loan__member")
        .order_by("-declenche_at")
    )

    statut = (request.query_params.get("statut") or "").strip()
    if statut:
        qs = qs.filter(statut=statut)

    open_filter = (request.query_params.get("open") or "").lower()
    if open_filter in ("true", "1", "yes"):
        qs = qs.filter(
            statut__in=[
                JudicialEscalation.Statut.EN_INSTANCE,
                JudicialEscalation.Statut.DECISION_RENDUE,
            ]
        )

    member_id = request.query_params.get("member")
    if member_id:
        qs = qs.filter(loan__member_id=member_id)

    q = (request.query_params.get("q") or "").strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(loan__numero_dossier__icontains=q)
            | Q(loan__member__nom__icontains=q)
            | Q(loan__member__prenom__icontains=q)
            | Q(loan__member__numero_membre__icontains=q)
        )

    count = qs.count()
    rows = [_row(e) for e in qs[:200]]
    return Response({"count": count, "results": rows})


# ---------------------------------------------------------------------------
# GET /loans/admin/escalations/<id>/ — détail
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — crédits éligibles à une escalade judiciaire",
    description=(
        "Crédits sur lesquels l'admin peut ouvrir une escalade : saisie sur "
        "épargne déjà tentée (`poursuite_judiciaire_at` posé), reliquat > 0, "
        "et aucune escalade existante. Sans cet endpoint, l'ouverture manuelle "
        "obligeait à deviner un id de crédit."
    ),
    responses={200: OpenApiResponse(description="`{ count, results: [...] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_escalation_candidates(request):
    qs = (
        Loan.objects.select_related("member")
        .filter(
            poursuite_judiciaire_at__isnull=False,
            solde_restant__gt=0,
            judicial_escalation__isnull=True,
        )
        .order_by("poursuite_judiciaire_at")
    )
    results = [
        {
            "loan_id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "member_nom": full_name(loan.member.prenom, loan.member.nom),
            "member_numero": loan.member.numero_membre,
            "solde_restant": str(loan.solde_restant),
            "poursuite_judiciaire_at": (
                loan.poursuite_judiciaire_at.isoformat()
                if loan.poursuite_judiciaire_at
                else None
            ),
        }
        for loan in qs[:200]
    ]
    return Response({"count": len(results), "results": results})


@extend_schema(
    tags=["loans"],
    summary="🔒 Staff — détail d'une escalade judiciaire",
    responses={200: OpenApiResponse(description="Détail")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_escalation_detail(request, pk: int):
    try:
        e = JudicialEscalation.objects.select_related(
            "loan", "loan__member"
        ).get(pk=pk)
    except JudicialEscalation.DoesNotExist:
        return Response({"detail": "Escalade introuvable."}, status=status.HTTP_404_NOT_FOUND)
    return Response(_row(e))


# ---------------------------------------------------------------------------
# POST /loans/admin/loans/<loan_id>/escalation/ — ouverture (phase D)
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — ouvre une escalade judiciaire sur un crédit (phase D)",
    description=(
        "Le crédit doit avoir `poursuite_judiciaire_at` non NULL (R1 saisie "
        "épargne déjà tentée) et un `solde_restant > 0`. Idempotent : si une "
        "escalade existe déjà pour ce crédit, la renvoie inchangée."
    ),
    request=JudicialOpenSerializer,
    responses={
        201: OpenApiResponse(description="Escalade ouverte"),
        200: OpenApiResponse(description="Escalade déjà existante (idempotent)"),
        400: OpenApiResponse(description="Guards non satisfaits"),
        404: OpenApiResponse(description="Crédit introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_open_escalation(request, loan_id: int):
    try:
        loan = Loan.objects.select_related("member").get(pk=loan_id)
    except Loan.DoesNotExist:
        return Response({"detail": "Crédit introuvable."}, status=status.HTTP_404_NOT_FOUND)

    existing_before = (
        JudicialEscalation.objects.filter(loan=loan).first() is not None
    )

    s = JudicialOpenSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    try:
        escalation = open_judicial_escalation(
            loan,
            motif=data["motif"],
            declenche_par=request.user,
            mode=data.get("mode", "manual"),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        _row(escalation),
        status=status.HTTP_200_OK if existing_before else status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# POST /loans/admin/escalations/<id>/decision/ — phase E1
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — enregistre la décision judiciaire (phase E1)",
    description=(
        "Transition EN_INSTANCE → DECISION_RENDUE. Pose `decision_date` et "
        "l'inventaire `biens_saisissables`. Idempotent si déjà DECISION_RENDUE."
    ),
    request=JudicialDecisionSerializer,
    responses={
        200: OpenApiResponse(description="Décision enregistrée"),
        400: OpenApiResponse(description="Transition impossible"),
        404: OpenApiResponse(description="Escalade introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_escalation_decision(request, pk: int):
    try:
        e = JudicialEscalation.objects.get(pk=pk)
    except JudicialEscalation.DoesNotExist:
        return Response({"detail": "Escalade introuvable."}, status=status.HTTP_404_NOT_FOUND)

    s = JudicialDecisionSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    try:
        e = record_judicial_decision(
            e,
            decision_date=s.validated_data["decision_date"],
            biens_saisissables=[
                _bien_to_dict(b) for b in s.validated_data.get("biens_saisissables") or []
            ],
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    e.refresh_from_db()
    return Response(_row(e))


# ---------------------------------------------------------------------------
# POST /loans/admin/escalations/<id>/execution/ — phase E2
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — exécute la saisie biens (phase E2)",
    description=(
        "Transition DECISION_RENDUE → EXECUTEE. Décrémente `Loan.solde_restant` "
        "du `montant_recouvre`, clamp pour ne pas passer en négatif. Clôture "
        "le crédit si solde tombe à 0. Idempotent si déjà EXECUTEE."
    ),
    request=JudicialExecutionSerializer,
    responses={
        200: OpenApiResponse(description="Exécution enregistrée"),
        400: OpenApiResponse(description="Transition impossible"),
        404: OpenApiResponse(description="Escalade introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_escalation_execution(request, pk: int):
    try:
        e = JudicialEscalation.objects.get(pk=pk)
    except JudicialEscalation.DoesNotExist:
        return Response({"detail": "Escalade introuvable."}, status=status.HTTP_404_NOT_FOUND)

    s = JudicialExecutionSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    try:
        e = record_judicial_execution(
            e,
            execution_date=s.validated_data["execution_date"],
            montant_recouvre=s.validated_data["montant_recouvre"],
            biens_saisis=[
                _bien_to_dict(b) for b in s.validated_data.get("biens_saisis") or []
            ],
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    e.refresh_from_db()
    return Response(_row(e))


# ---------------------------------------------------------------------------
# POST /loans/admin/escalations/<id>/classer/ — abandon
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["loans"],
    summary="🔒 Admin — classer sans suite (irrécouvrable)",
    description=(
        "Abandon administratif. Possible depuis EN_INSTANCE ou DECISION_RENDUE. "
        "Le crédit garde son solde résiduel (à passer en perte par compta). "
        "Idempotent."
    ),
    request=JudicialClasserSerializer,
    responses={
        200: OpenApiResponse(description="Classée sans suite"),
        400: OpenApiResponse(description="Transition impossible"),
        404: OpenApiResponse(description="Escalade introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_escalation_classer(request, pk: int):
    try:
        e = JudicialEscalation.objects.get(pk=pk)
    except JudicialEscalation.DoesNotExist:
        return Response({"detail": "Escalade introuvable."}, status=status.HTTP_404_NOT_FOUND)

    s = JudicialClasserSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    try:
        e = classer_sans_suite(e, motif=s.validated_data["motif"])
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    e.refresh_from_db()
    return Response(_row(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bien_to_dict(b) -> dict:
    """Normalise un BienItem en dict JSON-serializable (Decimal → str)."""
    return {
        "description": b["description"],
        "valeur_estimee": (
            str(b["valeur_estimee"]) if b.get("valeur_estimee") is not None else None
        ),
    }
