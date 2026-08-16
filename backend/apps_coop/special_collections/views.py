"""Endpoints collectes particulières — membre + admin.

Membre :
  GET  /special-collections/                 → mes participations (statut+solde)
  POST /special-collections/request/         → demande de participation
  GET  /special-collections/<type>/transactions/ → ledger d'une collecte
  POST /special-collections/transfer/        → transfert depuis épargne classique

Admin (IsStaff) :
  GET  /admin/special-collections/           → toutes les participations (filtres)
  GET  /admin/special-collections/<id>/      → détail + transactions
  POST /admin/special-collections/<id>/validate/
  POST /admin/special-collections/<id>/reject/
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.permissions import IsMember, IsStaff

from .models import SpecialCollectionMembership, SpecialCollectionTransaction
from .serializers import (
    ParticipationRequestSerializer,
    RejectSerializer,
    SpecialCollectionAdminSerializer,
    SpecialCollectionMembershipSerializer,
    SpecialCollectionTransactionSerializer,
    TransferSerializer,
)
from .services import (
    SpecialCollectionError,
    reject_participation,
    request_participation,
    transfer_from_classic,
    validate_participation,
)


# ── Membre ────────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsMember])
def my_collections(request):
    """Liste des participations du membre (une par type au plus)."""
    qs = SpecialCollectionMembership.objects.filter(member=request.user.member)
    return Response(SpecialCollectionMembershipSerializer(qs, many=True).data)


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
    membership = SpecialCollectionMembership.objects.filter(
        member=request.user.member, type=type
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


# ── Admin ─────────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list(request):
    """Toutes les participations, filtrables par ``type`` et ``statut``."""
    qs = SpecialCollectionMembership.objects.select_related("member").all()
    type_ = request.query_params.get("type")
    statut = request.query_params.get("statut")
    if type_:
        qs = qs.filter(type=type_)
    if statut:
        qs = qs.filter(statut=statut)
    return Response(SpecialCollectionAdminSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsStaff])
def admin_detail(request, pk: int):
    membership = get_object_or_404(
        SpecialCollectionMembership.objects.select_related("member"), pk=pk
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
