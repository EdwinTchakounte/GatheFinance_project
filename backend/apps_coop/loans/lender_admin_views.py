"""Admin views pour piloter le pool de tranches preteur (LA-1, LA-2, LA-3).

Permet a l'admin de :
  . Visualiser le pool de tranches DISPONIBLE (LA-1)
  . Composer manuellement le funding d'un Loan en cherry-pickant les
    tranches (LA-2 + LA-3).
  . Splitter une tranche en cas d'engagement partiel.

Permission : IsAdmin (groupe staff dedie).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import client_ip, record as record_audit
from apps_coop.members.permissions import IsAdmin
from apps_coop.savings.models import LenderTranche
from apps_coop.loans.models import Loan


# ---------------------------------------------------------------------------
# Serializers helpers (inline pour rester local — pas reutilises ailleurs)
# ---------------------------------------------------------------------------

def _serialize_tranche(t: LenderTranche) -> dict:
    user = getattr(t.member, "user", None)
    return {
        "id": t.id,
        "member": {
            "id": t.member.id,
            "numero_membre": t.member.numero_membre,
            "nom": t.member.nom or "",
            "prenom": t.member.prenom or "",
            "email": getattr(user, "email", "") if user else "",
        },
        "montant": str(t.montant),
        "statut": t.statut,
        "statut_display": t.get_statut_display(),
        "engaged_in_loan_id": t.engaged_in_loan_id,
        "engaged_in_loan_dossier": (
            t.engaged_in_loan.numero_dossier if t.engaged_in_loan_id else None
        ),
        "engaged_at": t.engaged_at.isoformat() if t.engaged_at else None,
        "released_at": t.released_at.isoformat() if t.released_at else None,
        "created_at": t.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# LA-1 . Liste pool preteurs + totalisateur reserve mobilisable
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_list_lender_tranches(request):
    """Liste les tranches preteur avec filtres optionnels.

    Query params :
      - statut : disponible (default) / engagee / liberee / annulee / all
      - member_id : filtre sur un membre precis
      - q : recherche par numero_membre / nom (icontains)
      - montant_min : seuil min en XAF
      - montant_max : seuil max en XAF
    """
    qs = (
        LenderTranche.objects.select_related("member__user", "engaged_in_loan")
        .order_by("-created_at")
    )
    statut = (request.query_params.get("statut") or "disponible").lower()
    if statut and statut != "all":
        qs = qs.filter(statut=statut)
    member_id = request.query_params.get("member_id")
    if member_id:
        qs = qs.filter(member_id=member_id)
    q = (request.query_params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            member__numero_membre__icontains=q,
        ) | qs.filter(
            member__nom__icontains=q,
        ) | qs.filter(
            member__prenom__icontains=q,
        )
    try:
        if request.query_params.get("montant_min"):
            qs = qs.filter(montant__gte=Decimal(request.query_params["montant_min"]))
        if request.query_params.get("montant_max"):
            qs = qs.filter(montant__lte=Decimal(request.query_params["montant_max"]))
    except (InvalidOperation, ValueError):
        return Response(
            {"detail": "Parametre montant_min/max invalide."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    limit = min(int(request.query_params.get("limit", 200)), 500)
    items = [_serialize_tranche(t) for t in qs[:limit]]
    return Response({"items": items, "count": len(items)})


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_lender_pool_summary(request):
    """Totaux par statut : nb tranches + total montant.

    Utilise sur le dashboard et en en-tete de /admin/lender-tranches.
    """
    rows = list(
        LenderTranche.objects.values("statut").annotate(
            n=Count("id"),
            total=Sum("montant"),
        )
    )
    summary = {
        "disponible": {"n": 0, "total": "0"},
        "engagee": {"n": 0, "total": "0"},
        "liberee": {"n": 0, "total": "0"},
        "annulee": {"n": 0, "total": "0"},
    }
    for r in rows:
        summary[r["statut"]] = {"n": r["n"], "total": str(r["total"] or 0)}
    return Response(summary)


# ---------------------------------------------------------------------------
# LA-2 / LA-3 . Composer le funding manuellement
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_compose_funding_manual(request, pk: int):
    """Engage manuellement des tranches preteur sur un Loan donne.

    Payload :
        {
            "selections": [
                {"tranche_id": 12, "montant": "50000"},
                {"tranche_id": 14, "montant": "30000"}
            ]
        }

    Regles :
      . Le total des selections doit etre <= loan.montant (capital).
      . Chaque tranche selectionnee doit etre DISPONIBLE.
      . Si montant < tranche.montant, la tranche est splittee en deux :
          - une nouvelle tranche DISPONIBLE pour le reste,
          - la tranche d'origine voit son montant ajuste et passe en ENGAGEE.
      . Si montant == tranche.montant, la tranche passe entierement en
        ENGAGEE avec engaged_in_loan = loan.
      . Tout est atomique : si une selection echoue, rien n'est engage.
    """
    try:
        loan = Loan.objects.select_for_update().get(pk=pk)
    except Loan.DoesNotExist:
        return Response({"detail": "Loan introuvable."}, status=status.HTTP_404_NOT_FOUND)

    selections = request.data.get("selections", [])
    if not selections or not isinstance(selections, list):
        return Response(
            {"detail": "Au moins une selection est requise."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validation totaux + parsing decimal
    parsed: list[tuple[int, Decimal]] = []
    total = Decimal("0")
    try:
        for sel in selections:
            tranche_id = int(sel["tranche_id"])
            montant = Decimal(str(sel["montant"]))
            if montant <= 0:
                raise ValueError("montant doit etre > 0")
            parsed.append((tranche_id, montant))
            total += montant
    except (KeyError, ValueError, InvalidOperation) as exc:
        return Response(
            {"detail": f"Selection invalide : {exc}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if total > loan.montant:
        return Response(
            {
                "detail": (
                    f"Total selectionne {total} XAF depasse le capital du "
                    f"credit {loan.montant} XAF."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    n_engaged = n_split = 0
    with transaction.atomic():
        for tranche_id, montant in parsed:
            try:
                t = LenderTranche.objects.select_for_update().get(pk=tranche_id)
            except LenderTranche.DoesNotExist:
                return Response(
                    {"detail": f"Tranche {tranche_id} introuvable."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if t.statut != LenderTranche.Statut.DISPONIBLE:
                return Response(
                    {
                        "detail": (
                            f"Tranche #{tranche_id} non disponible "
                            f"(statut actuel : {t.statut})."
                        ),
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if montant > t.montant:
                return Response(
                    {
                        "detail": (
                            f"Tranche #{tranche_id} : montant demande "
                            f"{montant} > montant disponible {t.montant}."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Split si engagement partiel.
            if montant < t.montant:
                LenderTranche.objects.create(
                    member=t.member,
                    montant=t.montant - montant,
                    statut=LenderTranche.Statut.DISPONIBLE,
                )
                t.montant = montant
                n_split += 1

            t.statut = LenderTranche.Statut.ENGAGEE
            t.engaged_in_loan = loan
            t.engaged_at = now
            t.save(update_fields=[
                "montant", "statut", "engaged_in_loan", "engaged_at", "updated_at",
            ])
            n_engaged += 1

    record_audit(
        action="loan.funding_composed_manual",
        entite_type="Loan",
        entite_id=loan.id,
        user=request.user,
        details={
            "loan_dossier": loan.numero_dossier,
            "total_engage": str(total),
            "n_tranches": n_engaged,
            "n_split": n_split,
        },
        ip=client_ip(request),
    )

    return Response(
        {
            "status": "ok",
            "loan_id": loan.id,
            "loan_dossier": loan.numero_dossier,
            "n_tranches_engagees": n_engaged,
            "n_tranches_splittees": n_split,
            "total_engage": str(total),
            "capital_loan": str(loan.montant),
            "reste_a_couvrir": str(loan.montant - total),
        },
        status=status.HTTP_200_OK,
    )
