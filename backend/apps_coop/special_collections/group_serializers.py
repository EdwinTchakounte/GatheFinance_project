"""Serializers des tontines de groupe (réunions)."""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    GroupTontine,
    GroupTontineLoan,
    GroupTontineMember,
    GroupTontineRole,
    GroupTontineTransaction,
)


class GroupRoleSerializer(serializers.ModelSerializer):
    """Rôle personnalisé de réunion (nom + actions cochées)."""

    class Meta:
        model = GroupTontineRole
        fields = [
            "id", "nom",
            "can_manage_funds", "can_grant_loan", "can_manage_roster",
            "can_record_cotisation", "can_close",
        ]


class GroupMemberSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    member_id = serializers.IntegerField(source="member.id", read_only=True)
    numero_membre = serializers.CharField(source="member.numero_membre", read_only=True)
    nom = serializers.CharField(source="member.nom", read_only=True)
    prenom = serializers.CharField(source="member.prenom", read_only=True)
    custom_role_id = serializers.IntegerField(source="custom_role.id", read_only=True, default=None)
    custom_role_nom = serializers.CharField(source="custom_role.nom", read_only=True, default="")
    # Actions effectives du membre (rôle intégré + rôle custom cumulés).
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = GroupTontineMember
        fields = [
            "id", "member_id", "numero_membre", "nom", "prenom",
            "role", "role_display", "custom_role_id", "custom_role_nom",
            "permissions", "actif",
        ]

    def get_permissions(self, obj) -> dict:
        from .group_services import member_permissions

        return member_permissions(obj.group, obj.member)


class GroupLoanSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    member_id = serializers.IntegerField(source="member.id", read_only=True)
    numero_membre = serializers.CharField(source="member.numero_membre", read_only=True)
    nom = serializers.CharField(source="member.nom", read_only=True)
    prenom = serializers.CharField(source="member.prenom", read_only=True)
    # Avaliste INFORMATIF (membre du roster OU nom libre). Sans impact financier.
    avaliste_id = serializers.IntegerField(source="avaliste.id", read_only=True, default=None)
    avaliste_display = serializers.SerializerMethodField()

    class Meta:
        model = GroupTontineLoan
        fields = [
            "id", "member_id", "numero_membre", "nom", "prenom",
            "montant", "solde_restant", "statut", "statut_display",
            "avaliste_id", "avaliste_nom", "avaliste_display", "created_at",
        ]

    def get_avaliste_display(self, obj) -> str:
        if obj.avaliste_id:
            a = obj.avaliste
            return f"{a.prenom} {a.nom}".strip() or a.numero_membre
        return obj.avaliste_nom or ""


class GroupTransactionSerializer(serializers.ModelSerializer):
    type_op_display = serializers.CharField(source="get_type_op_display", read_only=True)
    date_effective = serializers.DateTimeField(read_only=True)
    member_nom = serializers.CharField(source="member.nom", read_only=True, default="")
    member_prenom = serializers.CharField(source="member.prenom", read_only=True, default="")
    # Qui a effectué/validé l'action (traçabilité affichée aux membres).
    acted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = GroupTontineTransaction
        fields = [
            "id", "type_op", "type_op_display", "montant", "solde_apres",
            "libelle", "date_effective", "member_nom", "member_prenom",
            "acted_by_name", "created_at",
        ]

    def get_acted_by_name(self, obj) -> str:
        from .group_services import actor_name

        return actor_name(obj.acted_by) if obj.acted_by_id else ""


class GroupTontineSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = GroupTontine
        fields = [
            "id", "nom", "description", "solde", "montant_cotisation",
            "statut", "statut_display", "is_open", "members_count", "created_at",
            "closed_at",
        ]

    def get_members_count(self, obj) -> int:
        return obj.members.filter(actif=True).count()
