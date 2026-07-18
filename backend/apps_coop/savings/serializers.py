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
            "end_of_month_preference",
            "payout_phone",
            "payout_network",
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
    # Part librement retirable (= solde − placements encore actifs) et montant
    # bloqué en placement. Le portail/mobile s'en servent pour afficher le
    # « disponible au retrait » et empêcher un retrait d'entamer le placement.
    solde_libre = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True,
    )
    solde_placement_actif = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True,
    )
    # Réforme garantie 2026 : part gelée par des engagements crédit (caution
    # avaliste + collatéral demandeur) et disponible réel au retrait
    # (= solde − max(placement, gel garantie)).
    montant_gele_credit = serializers.SerializerMethodField()
    solde_disponible_retrait = serializers.SerializerMethodField()
    # True tant que CE membre peut placer : verrou global (date-limite + toggle)
    # ET fenêtre par membre (N premiers mois d'ancienneté, défaut 6). Les clients
    # masquent le choix « placement » quand false → tout versement va en LIBRE.
    placement_open = serializers.SerializerMethodField()
    # Nombre de mois de la fenêtre d'éligibilité (pour l'affichage côté client :
    # « placement ouvert les 6 premiers mois »).
    placement_eligibility_months = serializers.SerializerMethodField()

    class Meta:
        model = ClassicSavingsAccount
        fields = (
            "id", "solde", "solde_libre", "solde_placement_actif",
            "montant_gele_credit", "solde_disponible_retrait",
            "placement_open", "placement_eligibility_months",
            "date_ouverture", "config", "transactions_recentes",
        )
        read_only_fields = fields

    def get_placement_open(self, obj) -> bool:
        from .placement import placement_open_for_member

        return placement_open_for_member(obj.member)

    def get_placement_eligibility_months(self, obj) -> int:
        from .placement import placement_eligibility_months

        return placement_eligibility_months()

    def get_montant_gele_credit(self, obj: ClassicSavingsAccount):
        from apps_coop.loans.avaliste_services import member_frozen_guarantee

        return str(member_frozen_guarantee(obj.member))

    def get_solde_disponible_retrait(self, obj: ClassicSavingsAccount):
        from .services import classic_withdrawable

        return str(classic_withdrawable(obj))

    def get_transactions_recentes(self, obj: ClassicSavingsAccount):
        recent = obj.transactions.order_by("-date", "-id")[:10]
        return ClassicSavingsTransactionReadSerializer(recent, many=True).data

    def get_config(self, obj):
        return ClassicSavingsConfigSerializer(ClassicSavingsConfig.get_solo()).data


class WithdrawalRequestCreateSerializer(serializers.Serializer):
    """Body de POST /api/v1/savings/withdrawal/ — membre actif.

    Le membre choisit son canal :
      • ``mode_paiement = momo`` → fournir ``recipient_phone`` + ``network``
      • ``mode_paiement = presentiel`` → retrait espèces à l'agence
    """

    montant = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1)
    motif = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    source = serializers.ChoiceField(
        choices=WithdrawalRequest.Source.choices,
        default=WithdrawalRequest.Source.COLLECTE,
        help_text="Produit source : collecte journalière ou épargne classique (part libre).",
    )
    mode_paiement = serializers.ChoiceField(
        choices=WithdrawalRequest.ModePaiement.choices,
        default=WithdrawalRequest.ModePaiement.PRESENTIEL,
    )
    recipient_phone = serializers.CharField(
        max_length=32, required=False, allow_blank=True,
        help_text="Numéro Mobile Money — requis si mode_paiement = momo.",
    )
    network = serializers.ChoiceField(
        choices=WithdrawalRequest.Network.choices,
        required=False, allow_blank=True,
        help_text="Réseau MOMO — requis si mode_paiement = momo.",
    )

    def validate(self, attrs):
        mode = attrs.get("mode_paiement", WithdrawalRequest.ModePaiement.PRESENTIEL)
        if mode == WithdrawalRequest.ModePaiement.MOMO:
            if not (attrs.get("recipient_phone") or "").strip():
                raise serializers.ValidationError(
                    {"recipient_phone": "Requis pour un retrait Mobile Money."}
                )
            if not attrs.get("network"):
                raise serializers.ValidationError(
                    {"network": "Réseau requis pour un retrait Mobile Money."}
                )
        return attrs


class WithdrawalRequestReadSerializer(serializers.ModelSerializer):
    """Vue compacte d'une demande de retrait."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    mode_paiement_display = serializers.CharField(
        source="get_mode_paiement_display", read_only=True,
    )
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    recipient_phone_masked = serializers.SerializerMethodField()

    class Meta:
        model = WithdrawalRequest
        fields = (
            "id", "montant", "motif",
            "source", "source_display",
            "statut", "statut_display",
            "mode_paiement", "mode_paiement_display",
            "recipient_phone_masked", "network",
            "motif_rejet",
            "date_demande", "date_decision",
            "handed_over_at",
        )
        read_only_fields = fields

    def get_recipient_phone_masked(self, obj: WithdrawalRequest) -> str:
        p = obj.recipient_phone or ""
        if len(p) < 6:
            return ""
        return p[:4] + "***" + p[-2:]


class WithdrawalDecideSerializer(serializers.Serializer):
    """Body de POST /api/v1/admin/withdrawals/<id>/decide/ — staff."""

    decision = serializers.ChoiceField(choices=["approuvee", "rejetee"])
    motif_rejet = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["decision"] == "rejetee" and not (attrs.get("motif_rejet") or "").strip():
            raise serializers.ValidationError({"motif_rejet": "Requis pour rejeter."})
        return attrs


class WithdrawalHandoverSerializer(serializers.Serializer):
    """Body de POST /api/v1/admin/withdrawals/<id>/mark-paid/ — staff confirme
    qu'il a remis les espèces au membre (retrait présentiel)."""

    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)
