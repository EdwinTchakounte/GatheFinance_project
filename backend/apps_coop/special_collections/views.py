"""Endpoints collectes particulières — membre + admin (par cycles).

Membre :
  GET  /special-collections/                 → par type : cycle ouvert + ma participation
  POST /special-collections/request/         → demande (rattachée au cycle ouvert)
  GET  /special-collections/<type>/transactions/ → ledger (cycle ouvert)
  POST /special-collections/transfer/        → transfert depuis épargne classique

Admin (IsStaff) :
  GET  /special-collections/admin/                 → participations (filtres type/statut/cycle)
  GET  /special-collections/admin/<id>/            → détail participation + transactions
  POST /special-collections/admin/<id>/validate/
  POST /special-collections/admin/<id>/reject/
  GET  /special-collections/admin/cycles/          → cycles (filtre type)
  POST /special-collections/admin/cycles/          → ouvrir un cycle (clôt le précédent)
  GET  /special-collections/admin/cycles/<id>/     → détail cycle + rapprochement
  POST /special-collections/admin/cycles/<id>/close/
"""
from __future__ import annotations

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.permissions import IsMember, IsStaff

from .models import (
    SpecialCollectionCycle,
    SpecialCollectionMembership,
)
from .serializers import (
    OpenCycleSerializer,
    ParticipationRequestSerializer,
    RejectSerializer,
    SpecialCollectionAdminSerializer,
    SpecialCollectionCycleSerializer,
    SpecialCollectionMembershipSerializer,
    SpecialCollectionTransactionSerializer,
    TransferSerializer,
)
from .services import (
    SpecialCollectionError,
    close_cycle,
    current_open_cycle,
    decaisser_participation,
    member_carnet_for,
    open_cycle,
    open_cycles,
    reject_participation,
    request_participation,
    transfer_from_classic,
    validate_participation,
)


# ── Membre ────────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsMember])
def my_collections(request):
    """Pour chaque type : la LISTE des collectes ouvertes (plusieurs possibles),
    chacune avec ma participation, + si j'ai le carnet requis pour verser."""
    member = request.user.member
    out = []
    for type_, label in SpecialCollectionMembership.Type.choices:
        has_carnet = member_carnet_for(member, type_) is not None
        cycles_out = []
        for cycle in open_cycles(type_):
            membership = SpecialCollectionMembership.objects.filter(
                member=member, cycle=cycle
            ).first()
            cycles_out.append(
                {
                    "cycle": SpecialCollectionCycleSerializer(cycle).data,
                    "membership": (
                        SpecialCollectionMembershipSerializer(membership).data
                        if membership
                        else None
                    ),
                }
            )
        out.append(
            {
                "type": type_,
                "type_display": label,
                # Carnet du type acheté ? (prérequis pour verser)
                "has_carnet": has_carnet,
                "cycles": cycles_out,
                # RÉTRO-COMPAT ancienne APK (lit `cycle`/`membership` au niveau
                # du type) : on expose la collecte ouverte la plus récente. La
                # nouvelle app utilise `cycles`. À retirer une fois l'APK à jour
                # partout.
                "cycle": cycles_out[0]["cycle"] if cycles_out else None,
                "membership": cycles_out[0]["membership"] if cycles_out else None,
            }
        )
    return Response(out)


@api_view(["POST"])
@permission_classes([IsMember])
def request_collection(request):
    ser = ParticipationRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    try:
        membership = request_participation(
            member=request.user.member,
            type=data["type"],
            cycle_id=data.get("cycle_id"),
            objectif=data["objectif"],
            montant_cible=data.get("montant_cible"),
            form_payload=data.get("extra") or {},
        )
    except SpecialCollectionError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        SpecialCollectionMembershipSerializer(membership).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsMember])
def my_collection_transactions(request, type: str):
    """Ledger d'une collecte. ``?cycle=<id>`` cible une collecte précise ;
    sinon la plus récente ouverte."""
    cycle_id = request.query_params.get("cycle")
    if cycle_id:
        cycle = SpecialCollectionCycle.objects.filter(pk=cycle_id, type=type).first()
    else:
        cycle = current_open_cycle(type)
    if cycle is None:
        return Response([])
    membership = SpecialCollectionMembership.objects.filter(
        member=request.user.member, cycle=cycle
    ).first()
    if membership is None:
        return Response([])
    rows = membership.transactions.all()
    return Response(SpecialCollectionTransactionSerializer(rows, many=True).data)


@api_view(["POST"])
@permission_classes([IsMember])
def transfer(request):
    ser = TransferSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    try:
        row = transfer_from_classic(
            member=request.user.member,
            type=data["type"],
            cycle_id=data.get("cycle_id"),
            montant=data["montant"],
        )
    except SpecialCollectionError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        SpecialCollectionTransactionSerializer(row).data,
        status=status.HTTP_201_CREATED,
    )


# ── Admin — participations ────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list(request):
    """Participations, filtrables par ``type``, ``statut`` et ``cycle``."""
    qs = SpecialCollectionMembership.objects.select_related("member", "cycle").all()
    type_ = request.query_params.get("type")
    statut = request.query_params.get("statut")
    cycle_id = request.query_params.get("cycle")
    if type_:
        qs = qs.filter(type=type_)
    if statut:
        qs = qs.filter(statut=statut)
    if cycle_id:
        qs = qs.filter(cycle_id=cycle_id)
    return Response(SpecialCollectionAdminSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsStaff])
def admin_detail(request, pk: int):
    membership = get_object_or_404(
        SpecialCollectionMembership.objects.select_related("member", "cycle"), pk=pk
    )
    data = SpecialCollectionAdminSerializer(membership).data
    data["transactions"] = SpecialCollectionTransactionSerializer(
        membership.transactions.all(), many=True
    ).data
    return Response(data)


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_validate(request, pk: int):
    membership = get_object_or_404(SpecialCollectionMembership, pk=pk)
    validate_participation(membership, by=request.user)
    return Response(SpecialCollectionAdminSerializer(membership).data)


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_reject(request, pk: int):
    ser = RejectSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    membership = get_object_or_404(SpecialCollectionMembership, pk=pk)
    reject_participation(membership, motif=ser.validated_data.get("motif", ""), by=request.user)
    return Response(SpecialCollectionAdminSerializer(membership).data)


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_decaisser(request, pk: int):
    """Décaissement d'une participation : débite le solde et sort l'argent
    (vers l'épargne classique du membre OU en espèces agence)."""
    from decimal import Decimal, InvalidOperation

    membership = get_object_or_404(SpecialCollectionMembership, pk=pk)
    try:
        montant = Decimal(str(request.data.get("montant") or "0"))
    except (InvalidOperation, TypeError):
        return Response({"detail": "Montant invalide."}, status=status.HTTP_400_BAD_REQUEST)
    destination = str(request.data.get("destination") or "epargne")
    try:
        decaisser_participation(
            member=membership.member,
            cycle_id=membership.cycle_id,
            montant=montant,
            destination=destination,
            note=str(request.data.get("note") or ""),
            by=request.user,
        )
    except SpecialCollectionError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    membership.refresh_from_db()
    return Response(SpecialCollectionAdminSerializer(membership).data)


# ── Admin — cycles ────────────────────────────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([IsStaff])
def admin_cycles(request):
    if request.method == "POST":
        ser = OpenCycleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            cycle = open_cycle(
                type=data["type"],
                nom=data["nom"],
                description=data.get("description", ""),
                montant_minimal=data.get("montant_minimal"),
                date_debut=data.get("date_debut"),
                date_fin=data.get("date_fin"),
                by=request.user,
            )
        except SpecialCollectionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            SpecialCollectionCycleSerializer(cycle).data,
            status=status.HTTP_201_CREATED,
        )

    qs = SpecialCollectionCycle.objects.all()
    type_ = request.query_params.get("type")
    if type_:
        qs = qs.filter(type=type_)
    # Enrichit chaque cycle du nb de participants + total collecté (rapprochement).
    # Calcul PAR CYCLE (pas d'annotate Count+Sum combiné, dont le résultat peut
    # différer entre PostgreSQL et SQLite) : robuste et exact sur toute base.
    # Le nombre de cycles est petit → le coût est négligeable.
    rows = []
    for c in qs.order_by("-date_debut", "-id"):
        agg = c.memberships.aggregate(n=Count("id"), total=Sum("solde"))
        row = SpecialCollectionCycleSerializer(c).data
        row["participants"] = agg["n"] or 0
        row["total_collecte"] = str(agg["total"] or 0)
        rows.append(row)
    return Response(rows)


@api_view(["GET"])
@permission_classes([IsStaff])
def admin_cycle_detail(request, pk: int):
    """Détail d'un cycle + rapprochement (participants validés + total collecté)."""
    cycle = get_object_or_404(SpecialCollectionCycle, pk=pk)
    memberships = (
        SpecialCollectionMembership.objects.select_related("member")
        .filter(cycle=cycle)
        .order_by("member__nom", "member__prenom")
    )
    total = sum((m.solde for m in memberships), start=0) if memberships else 0
    data = SpecialCollectionCycleSerializer(cycle).data
    data["participants"] = SpecialCollectionAdminSerializer(memberships, many=True).data
    data["participants_count"] = memberships.count()
    data["total_collecte"] = str(total)
    return Response(data)


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_cycle_close(request, pk: int):
    cycle = get_object_or_404(SpecialCollectionCycle, pk=pk)
    close_cycle(cycle, by=request.user)
    return Response(SpecialCollectionCycleSerializer(cycle).data)
