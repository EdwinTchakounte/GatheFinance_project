"""Endpoints tontines de groupe (réunions) — admin + membres (rôles).

Admin (IsStaff) : créer/lister/détail, roster (ajout/retrait), rôle, clôture.
Membre (IsMember) : mes réunions + détail (si membre) ; président/trésorier :
versement bénéficiaire, prêt, remboursement, changement de rôle, clôture.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.models import Member
from apps_coop.members.permissions import IsMember, IsStaff

from . import group_services as gs
from .group_serializers import (
    GroupLoanSerializer,
    GroupMemberSerializer,
    GroupRoleSerializer,
    GroupTontineSerializer,
    GroupTransactionSerializer,
)
from .models import (
    GroupTontine,
    GroupTontineLoan,
    GroupTontineMember,
    GroupTontineRole,
)


def _detail_payload(group: GroupTontine, *, viewer_role=None, viewer_member=None) -> dict:
    # Re-lecture : après une action (cotiser/payout/prêt…), l'objet `group` de la
    # vue est périmé (la mutation a porté sur une autre instance verrouillée). On
    # relit pour renvoyer la cagnotte/le statut à jour.
    group.refresh_from_db()
    data = GroupTontineSerializer(group).data
    data["members"] = GroupMemberSerializer(
        group.members.filter(actif=True).select_related("member"), many=True
    ).data
    data["loans"] = GroupLoanSerializer(
        group.loans.select_related("member").all(), many=True
    ).data
    data["transactions"] = GroupTransactionSerializer(
        group.transactions.select_related("member").all()[:100], many=True
    ).data
    # Rôles personnalisés définis dans la réunion (avec leurs actions cochées).
    data["custom_roles"] = GroupRoleSerializer(
        group.custom_roles.all(), many=True
    ).data
    if viewer_role is not None:
        data["my_role"] = viewer_role
    if viewer_member is not None:
        # Permet à l'app de savoir quels prêts sont ceux du membre (bouton
        # « Rembourser mon prêt »).
        data["my_member_id"] = viewer_member.id
        # Actions dont dispose le viewer (pilote l'affichage des boutons).
        data["my_permissions"] = gs.member_permissions(group, viewer_member)
    return data


def _roster_from_payload(raw):
    """Construit une liste ``[{member, role}]`` depuis un payload d'API."""
    roster = []
    for entry in raw or []:
        member = Member.objects.filter(pk=entry.get("member_id")).first()
        if member is None:
            continue
        role = entry.get("role", GroupTontineMember.Role.MEMBRE)
        if role not in GroupTontineMember.Role.values:
            role = GroupTontineMember.Role.MEMBRE
        roster.append({"member": member, "role": role})
    return roster


# ── Admin ─────────────────────────────────────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([IsStaff])
def admin_groups(request):
    if request.method == "POST":
        roster = _roster_from_payload(request.data.get("roster"))
        try:
            group = gs.create_group(
                nom=request.data.get("nom") or "",
                description=request.data.get("description") or "",
                montant_cotisation=request.data.get("montant_cotisation"),
                roster=roster,
                by=request.user,
            )
        except gs.GroupTontineError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_detail_payload(group), status=status.HTTP_201_CREATED)

    groups = GroupTontine.objects.all()
    return Response(GroupTontineSerializer(groups, many=True).data)


@api_view(["GET"])
@permission_classes([IsStaff])
def admin_group_detail(request, pk: int):
    group = get_object_or_404(GroupTontine, pk=pk)
    return Response(_detail_payload(group))


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_group_add_member(request, pk: int):
    group = get_object_or_404(GroupTontine, pk=pk)
    member = get_object_or_404(Member, pk=request.data.get("member_id"))
    role = request.data.get("role", GroupTontineMember.Role.MEMBRE)
    gs.add_member(group, member, role=role, by=request.user)
    return Response(_detail_payload(group))


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_group_remove_member(request, pk: int):
    group = get_object_or_404(GroupTontine, pk=pk)
    member = get_object_or_404(Member, pk=request.data.get("member_id"))
    gs.remove_member(group, member, by=request.user)
    return Response(_detail_payload(group))


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_group_set_role(request, pk: int):
    group = get_object_or_404(GroupTontine, pk=pk)
    member = get_object_or_404(Member, pk=request.data.get("member_id"))
    try:
        gs.set_role(group, member, request.data.get("role"), by=request.user)
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group))


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_group_close(request, pk: int):
    group = get_object_or_404(GroupTontine, pk=pk)
    gs.close_group(group, by=request.user)
    return Response(GroupTontineSerializer(group).data)


# ── Membre / rôles ──────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsMember])
def my_groups(request):
    """Réunions dont je fais partie, avec mon rôle + la cagnotte."""
    member = request.user.member
    out = []
    for g in gs.groups_for_member(member):
        row = GroupTontineSerializer(g).data
        row["my_role"] = gs.role_of(g, member)
        out.append(row)
    return Response(out)


def _member_group_or_403(request, pk):
    """Retourne (group, member, role) si le membre appartient au groupe, sinon
    lève une Response 403/404 via exception maison."""
    group = GroupTontine.objects.filter(pk=pk).first()
    if group is None:
        return None, None, None
    member = request.user.member
    role = gs.role_of(group, member)
    return group, member, role


@api_view(["GET"])
@permission_classes([IsMember])
def group_detail(request, pk: int):
    group, member, role = _member_group_or_403(request, pk)
    if group is None:
        return Response({"detail": "Réunion introuvable."}, status=404)
    if role is None:
        return Response(
            {"detail": "Réunion réservée à ses membres."}, status=403
        )
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


@api_view(["POST"])
@permission_classes([IsMember])
def group_payout(request, pk: int):
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    beneficiary = Member.objects.filter(pk=request.data.get("beneficiary_id")).first()
    if beneficiary is None:
        return Response({"detail": "Bénéficiaire introuvable."}, status=404)
    try:
        gs.payout_beneficiary(
            group=group, beneficiary=beneficiary,
            montant=request.data.get("montant") or 0, by=member,
        )
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


@api_view(["POST"])
@permission_classes([IsMember])
def group_loan(request, pk: int):
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    borrower = Member.objects.filter(pk=request.data.get("member_id")).first()
    if borrower is None:
        return Response({"detail": "Membre introuvable."}, status=404)
    # Avaliste INFORMATIF : membre du roster (avaliste_id) OU nom libre.
    avaliste = None
    if request.data.get("avaliste_id"):
        avaliste = Member.objects.filter(pk=request.data.get("avaliste_id")).first()
    try:
        gs.grant_loan(
            group=group, member=borrower,
            montant=request.data.get("montant") or 0, by=member,
            avaliste=avaliste,
            avaliste_nom=request.data.get("avaliste_nom") or "",
        )
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


@api_view(["POST"])
@permission_classes([IsMember])
def group_loan_repay(request, pk: int, loan_id: int):
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    loan = GroupTontineLoan.objects.filter(pk=loan_id, group=group).first()
    if loan is None:
        return Response({"detail": "Prêt introuvable."}, status=404)
    try:
        gs.repay_loan(loan=loan, montant=request.data.get("montant") or 0, by=member)
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


@api_view(["POST"])
@permission_classes([IsMember])
def group_set_role(request, pk: int):
    """Change les rôles — président, ou tout membre habilité « gérer le roster »."""
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    if not gs.member_permissions(group, member).get("can_manage_roster"):
        return Response(
            {"detail": "Vous n'avez pas l'autorisation de gérer les rôles."},
            status=403,
        )
    target = Member.objects.filter(pk=request.data.get("member_id")).first()
    if target is None:
        return Response({"detail": "Membre introuvable."}, status=404)
    try:
        gs.set_role(group, target, request.data.get("role"), by=member)
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


@api_view(["POST"])
@permission_classes([IsMember])
def group_transfer_cotisation(request, pk: int):
    """Cotisation par prélèvement sur mon épargne classique disponible."""
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    try:
        gs.transfer_cotisation(
            group=group, member=member, montant=request.data.get("montant") or 0
        )
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


@api_view(["POST"])
@permission_classes([IsMember])
def group_close(request, pk: int):
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    if not gs.member_permissions(group, member).get("can_close"):
        return Response(
            {"detail": "Vous n'avez pas l'autorisation de clôturer cette réunion."},
            status=403,
        )
    gs.close_group(group, by=member)
    return Response(GroupTontineSerializer(group).data)


# ── Rôles personnalisés (actions rattachées) ─────────────────────────────────
def _role_perms_from_payload(data) -> dict:
    """Extrait le dict d'actions depuis le payload (accepte un sous-objet
    ``permissions`` ou des clés à plat)."""
    src = data.get("permissions") if isinstance(data.get("permissions"), dict) else data
    return {f: bool(src.get(f, False)) for f in GroupTontineRole.ACTION_FIELDS}


def _require_roster_perm(group, member):
    """None si OK, sinon une Response 403."""
    if not gs.member_permissions(group, member).get("can_manage_roster"):
        return Response(
            {"detail": "Vous n'avez pas l'autorisation de gérer les rôles."},
            status=403,
        )
    return None


@api_view(["POST"])
@permission_classes([IsMember])
def group_roles(request, pk: int):
    """Crée un rôle personnalisé (membre habilité « gérer le roster »)."""
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    denied = _require_roster_perm(group, member)
    if denied is not None:
        return denied
    try:
        gs.create_custom_role(
            group, request.data.get("nom"),
            _role_perms_from_payload(request.data), by=member,
        )
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


@api_view(["POST", "DELETE"])
@permission_classes([IsMember])
def group_role_detail(request, pk: int, role_id: int):
    """Met à jour (POST) ou supprime (DELETE) un rôle personnalisé."""
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    denied = _require_roster_perm(group, member)
    if denied is not None:
        return denied
    obj = GroupTontineRole.objects.filter(pk=role_id, group=group).first()
    if obj is None:
        return Response({"detail": "Rôle introuvable."}, status=404)
    if request.method == "DELETE":
        gs.delete_custom_role(obj, by=member)
        return Response(_detail_payload(group, viewer_role=role, viewer_member=member))
    try:
        gs.update_custom_role(
            obj,
            nom=request.data.get("nom"),
            permissions=(
                _role_perms_from_payload(request.data)
                if ("permissions" in request.data
                    or any(f in request.data for f in GroupTontineRole.ACTION_FIELDS))
                else None
            ),
            by=member,
        )
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


@api_view(["POST"])
@permission_classes([IsMember])
def group_assign_role(request, pk: int):
    """Attribue/retire un rôle personnalisé à un membre (habilité roster)."""
    group, member, role = _member_group_or_403(request, pk)
    if group is None or role is None:
        return Response({"detail": "Réunion réservée à ses membres."}, status=403)
    denied = _require_roster_perm(group, member)
    if denied is not None:
        return denied
    target = Member.objects.filter(pk=request.data.get("member_id")).first()
    if target is None:
        return Response({"detail": "Membre introuvable."}, status=404)
    custom_role = None
    if request.data.get("custom_role_id"):
        custom_role = GroupTontineRole.objects.filter(
            pk=request.data.get("custom_role_id"), group=group
        ).first()
        if custom_role is None:
            return Response({"detail": "Rôle introuvable."}, status=404)
    try:
        gs.assign_custom_role(group, target, custom_role, by=member)
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group, viewer_role=role, viewer_member=member))


# ── Rôles personnalisés — variante ADMIN (IsStaff) ───────────────────────────
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_group_roles(request, pk: int):
    group = get_object_or_404(GroupTontine, pk=pk)
    try:
        gs.create_custom_role(
            group, request.data.get("nom"),
            _role_perms_from_payload(request.data), by=request.user,
        )
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group))


@api_view(["POST", "DELETE"])
@permission_classes([IsStaff])
def admin_group_role_detail(request, pk: int, role_id: int):
    group = get_object_or_404(GroupTontine, pk=pk)
    obj = GroupTontineRole.objects.filter(pk=role_id, group=group).first()
    if obj is None:
        return Response({"detail": "Rôle introuvable."}, status=404)
    if request.method == "DELETE":
        gs.delete_custom_role(obj, by=request.user)
        return Response(_detail_payload(group))
    try:
        gs.update_custom_role(
            obj,
            nom=request.data.get("nom"),
            permissions=(
                _role_perms_from_payload(request.data)
                if ("permissions" in request.data
                    or any(f in request.data for f in GroupTontineRole.ACTION_FIELDS))
                else None
            ),
            by=request.user,
        )
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group))


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_group_assign_role(request, pk: int):
    group = get_object_or_404(GroupTontine, pk=pk)
    target = get_object_or_404(Member, pk=request.data.get("member_id"))
    custom_role = None
    if request.data.get("custom_role_id"):
        custom_role = GroupTontineRole.objects.filter(
            pk=request.data.get("custom_role_id"), group=group
        ).first()
        if custom_role is None:
            return Response({"detail": "Rôle introuvable."}, status=404)
    try:
        gs.assign_custom_role(group, target, custom_role, by=request.user)
    except gs.GroupTontineError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail_payload(group))
