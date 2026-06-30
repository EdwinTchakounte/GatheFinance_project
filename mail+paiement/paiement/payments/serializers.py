"""Serializers for the payments API.

Kept narrow: each endpoint has its own serializer, no shared mega-class.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Payment


_ALLOWED_INIT_TYPES = {
    Payment.Type.FRAIS_ADHESION,
    Payment.Type.FRAIS_INSCRIPTION,
    Payment.Type.EPARGNE,
    Payment.Type.EPARGNE_CLASSIQUE,
    Payment.Type.REMBOURSEMENT,
    Payment.Type.FRAIS_DEMANDE_CREDIT,
    # FRAIS_RECONDUCTION retiré : la reconduction est sans frais (Règlement).
    Payment.Type.FRAIS_CARNET,
}

_ALLOWED_NETWORKS = {"MTN", "ORANGE", "WAVE", "AIRTEL"}


class PaymentInitSerializer(serializers.Serializer):
    """POST /api/v1/payments/init/ body."""

    type = serializers.ChoiceField(choices=sorted(_ALLOWED_INIT_TYPES))
    montant = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=100)
    phone = serializers.CharField(max_length=32)
    network = serializers.CharField(max_length=16)
    # Optional links — only meaningful for remboursement / fees tied to a loan
    loan_id = serializers.IntegerField(required=False, allow_null=True)
    loan_installment_id = serializers.IntegerField(required=False, allow_null=True)
    # LOT 6 (refonte 2026) — multi-jours pré-payé sur la collecte journalière.
    # N = 1 : versement classique d'1 jour, montant libre ≥ collecte.min_per_day.
    # N > 1 : mode multi-jours, montant doit valoir EXACTEMENT
    #         N × collecte.min_per_day (validation côté view).
    # Plafond N ≤ collecte.prepay.max_days (défaut 30).
    nb_jours_couverts = serializers.IntegerField(
        required=False,
        min_value=1,
        default=1,
        help_text=(
            "Nombre de jours couverts par le versement (multi-jours pré-payé). "
            "Défaut 1. > 1 → montant figé à N × collecte.min_per_day."
        ),
    )
    # CH-3 (refonte 2026) — Sous-canal placement épargne classique.
    # Significatif uniquement quand type == EPARGNE_CLASSIQUE.
    is_placement = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "Pour type=epargne_classique : True = placement bloqué 12 mois "
            "(intérêt mensuel à la maturité), False = libre. Ignoré sinon."
        ),
    )

    def validate_network(self, value: str) -> str:
        upper = value.upper()
        if upper not in _ALLOWED_NETWORKS:
            raise serializers.ValidationError(
                f"Network {value!r} non supporté. Attendu : {sorted(_ALLOWED_NETWORKS)}."
            )
        return upper

    def validate_phone(self, value: str) -> str:
        digits = "".join(c for c in value if c.isdigit())
        if len(digits) < 9:
            raise serializers.ValidationError("Numéro de téléphone invalide.")
        return value


class PaymentReadSerializer(serializers.ModelSerializer):
    """Compact representation returned to the portal (read-only)."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "montant",
            "type",
            "type_display",
            "source",
            "statut",
            "statut_display",
            "provider_code",
            "reference_externe",
            "date_versement",
            "date_validation",
            "motif_rejet",
            "created_at",
            # LOT 6 (refonte 2026) — multi-jours pré-payé.
            "nb_jours_couverts",
            # CH-3 (refonte 2026) — épargne classique placement vs libre.
            "is_placement",
        )
        read_only_fields = fields
