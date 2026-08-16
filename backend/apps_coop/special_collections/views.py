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
    open_cycle,
    reject_participation,
    request_participation,
    transfer_from_classic,
    validate_participation,
)


# ── Membre ────────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsMember])
def my_collections(request):
    """Pour chaque type : le cycle ouvert (le cas échéant) et ma participation
    dans ce cycle (le cas échéant)."""
    member = request.user.member
    out = []
    for type_, _label in SpecialCollectionMembership.Type.choices:
        cycle = current_open_cycle(type_)
        membership = None
        if cycle is not None:
            membership = SpecialCollectionMembership.objects.filter(
                member=member, cycle=cycle
            ).first()
        out.append(
            {
                "type": type_,
                "type_display": dict(SpecialCollectionMembership.Type.choices)[type_],
                "cycle": SpecialCollectionCycleSerializer(cycle).data if cycle else None,
                "membership": (
                    SpecialCollectionMembershipSerializer(membership).data
                    if membership
                    else None
                ),
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
    qs = qs.annotate(
        participants=Count("memberships", distinct=True),
        total_collecte=Sum("memberships__solde"),
    )
    rows = []
    for c in qs:
        row = SpecialCollectionCycleSerializer(c).data
        row["participants"] = c.participants
        row["total_collecte"] = str(c.total_collecte or 0)
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
