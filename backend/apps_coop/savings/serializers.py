"""Serializers for the savings domain — read-only (deposits go through /payments/init/)."""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    ClassicSavingsAccount,
    ClassicSavingsConfig,
    ClassicSavingsTransaction,
    SavingsAccount,
    SavingsTransaction,
    WithdrawalRequest,
)


class SavingsTransactionReadSerializer(serializers.ModelSerializer):
    """Compact transaction representation for portal display."""

    type_display = serializers.CharField(source="get_type_op_display", read_only=True)

    class Meta:
        model = SavingsTransaction
        fields = ("id", "type_op", "type_display", "montant", "solde_apres", "date")
        read_only_fields = fields


class SavingsAccountReadSerializer(serializers.ModelSerializer):
    """Member's savings account snapshot — balance + recent activity.

    Used by ``GET /api/v1/savings/me/``. The portal calls this both at landing
    (« Tu as X XAF d'épargne ») and after a deposit confirmation to refresh
    the display.
    """

    transactions_recentes = serializers.SerializerMethodField()

    class Meta:
        model = SavingsAccount
        fields = (
            "id",
            "solde",
            "date_ouverture",
            "taux_interet_applique",
            "transactions_recentes",
        )
        read_only_fields = fields

    def get_transactions_recentes(self, obj: SavingsAccount):
        recent = obj.transactions.order_by("-date", "-id")[:10]
        return SavingsTransactionReadSerializer(recent, many=True).data


class ClassicSavingsConfigSerializer(serializers.ModelSerializer):
    """Config du produit épargne classique (lecture membre + édition staff)."""

    class Meta:
        model = ClassicSavingsConfig
        fields = (
            "actif",
            "libelle",
            "taux_interet_mensuel",
            "depot_min",
            "depot_max",
            "retrait_validation_requise",
        )


class ClassicSavingsTransactionReadSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_op_display", read_only=True)

    class Meta:
        model = ClassicSavingsTransaction
        fields = ("id", "type_op", "type_display", "montant", "solde_apres", "date")
        read_only_fields = fields


class ClassicSavingsAccountReadSerializer(serializers.ModelSerializer):
    """Snapshot du compte épargne classique du membre + config + activité récente."""

    transactions_recentes = serializers.SerializerMethodField()
    config = serializers.SerializerMethodField()

    class Meta:
        model = ClassicSavingsAccount
        fields = ("id", "solde", "date_ouverture", "config", "transactions_recentes")
        read_only_fields = fields

    def get_transactions_recentes(self, obj: ClassicSavingsAccount):
        recent = obj.transactions.order_by("-date", "-id")[:10]
        return ClassicSavingsTransactionReadSerializer(recent, many=True).data

    def get_config(self, obj):
        return ClassicSavingsConfigSerializer(ClassicSavingsConfig.get_solo()).data


class WithdrawalRequestCreateSerializer(serializers.Serializer):
    """Body de POST /api/v1/savings/withdrawal/ — membre actif."""

    montant = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1)
    motif = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class WithdrawalRequestReadSerializer(serializers.ModelSerializer):
    """Vue compacte d'une demande de retrait."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = (
            "id", "montant", "motif", "statut", "statut_display",
            "motif_rejet", "date_demande", "date_decision",
        )
        read_only_fields = fields


class WithdrawalDecideSerializer(serializers.Serializer):
    """Body de POST /api/v1/admin/withdrawals/<id>/decide/ — staff."""

    decision = serializers.ChoiceField(choices=["approuvee", "rejetee"])
    motif_rejet = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["decision"] == "rejetee" and not (attrs.get("motif_rejet") or "").strip():
            raise serializers.ValidationError({"motif_rejet": "Requis pour rejeter."})
        return attrs
