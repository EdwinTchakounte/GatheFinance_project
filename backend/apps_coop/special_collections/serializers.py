"""Serializers des collectes particulières (membre + admin)."""
from __future__ import annotations

from rest_framework import serializers

from .models import SpecialCollectionMembership, SpecialCollectionTransaction


class SpecialCollectionTransactionSerializer(serializers.ModelSerializer):
    type_op_display = serializers.CharField(source="get_type_op_display", read_only=True)

    class Meta:
        model = SpecialCollectionTransaction
        fields = [
            "id",
            "type_op",
            "type_op_display",
            "montant",
            "solde_apres",
            "libelle",
            "created_at",
        ]


class SpecialCollectionMembershipSerializer(serializers.ModelSerializer):
    """Vue membre d'une participation (statut + solde + objectif)."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = SpecialCollectionMembership
        fields = [
            "id",
            "type",
            "type_display",
            "statut",
            "statut_display",
            "is_active",
            "solde",
            "objectif",
            "montant_cible",
            "form_payload",
            "motif_rejet",
            "created_at",
            "validated_at",
        ]


class SpecialCollectionAdminSerializer(SpecialCollectionMembershipSerializer):
    """Vue admin : ajoute l'identité du membre participant."""

    member_id = serializers.IntegerField(source="member.id", read_only=True)
    numero_membre = serializers.CharField(source="member.numero_membre", read_only=True)
    member_nom = serializers.CharField(source="member.nom", read_only=True)
    member_prenom = serializers.CharField(source="member.prenom", read_only=True)

    class Meta(SpecialCollectionMembershipSerializer.Meta):
        fields = SpecialCollectionMembershipSerializer.Meta.fields + [
            "member_id",
            "numero_membre",
            "member_nom",
            "member_prenom",
        ]


class ParticipationRequestSerializer(serializers.Serializer):
    """Formulaire de demande (minimal, extensible via extra)."""

    type = serializers.ChoiceField(choices=SpecialCollectionMembership.Type.choices)
    objectif = serializers.CharField(max_length=2000)
    montant_cible = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    extra = serializers.DictField(required=False, default=dict)


class TransferSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=SpecialCollectionMembership.Type.choices)
    montant = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=1)


class RejectSerializer(serializers.Serializer):
    motif = serializers.CharField(max_length=2000, allow_blank=True, required=False, default="")
