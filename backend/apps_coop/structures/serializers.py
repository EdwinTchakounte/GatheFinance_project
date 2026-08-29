"""Serializers des structures employeur & paie."""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    PayrollRun,
    Structure,
    StructureEmployee,
    StructureTransaction,
)


class EmployeeSerializer(serializers.ModelSerializer):
    member_id = serializers.IntegerField(source="member.id", read_only=True)
    numero_membre = serializers.CharField(source="member.numero_membre", read_only=True)
    nom = serializers.CharField(source="member.nom", read_only=True)
    prenom = serializers.CharField(source="member.prenom", read_only=True)

    class Meta:
        model = StructureEmployee
        fields = [
            "id", "member_id", "numero_membre", "nom", "prenom",
            "poste", "attribution", "montant_paie", "actif",
        ]


class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = [
            "id", "periode", "total_verse", "employes_count", "created_at",
        ]


class StructureTxSerializer(serializers.ModelSerializer):
    type_op_display = serializers.CharField(source="get_type_op_display", read_only=True)
    date_effective = serializers.DateTimeField(read_only=True)
    member_nom = serializers.CharField(source="member.nom", read_only=True, default="")
    member_prenom = serializers.CharField(source="member.prenom", read_only=True, default="")
    acted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StructureTransaction
        fields = [
            "id", "type_op", "type_op_display", "montant", "solde_apres",
            "libelle", "date_effective", "member_nom", "member_prenom",
            "acted_by_name", "created_at",
        ]

    def get_acted_by_name(self, obj) -> str:
        u = obj.acted_by
        if u is None:
            return ""
        full = f"{u.first_name} {u.last_name}".strip()
        return full or (getattr(u, "email", "") or "")


class StructureSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    employees_count = serializers.SerializerMethodField()
    masse_salariale = serializers.SerializerMethodField()

    class Meta:
        model = Structure
        fields = [
            "id", "nom", "description", "solde", "statut", "statut_display",
            "is_active", "employees_count", "masse_salariale", "created_at",
            "closed_at",
        ]

    def get_employees_count(self, obj) -> int:
        return obj.employees.filter(actif=True).count()

    def get_masse_salariale(self, obj) -> str:
        from decimal import Decimal
        total = sum(
            (Decimal(e.montant_paie) for e in obj.employees.filter(actif=True)),
            Decimal("0"),
        )
        return str(total)


class StructureDetailSerializer(StructureSerializer):
    employees = serializers.SerializerMethodField()
    payroll_runs = serializers.SerializerMethodField()
    transactions = serializers.SerializerMethodField()

    class Meta(StructureSerializer.Meta):
        fields = StructureSerializer.Meta.fields + [
            "employees", "payroll_runs", "transactions",
        ]

    def get_employees(self, obj):
        return EmployeeSerializer(
            obj.employees.filter(actif=True).select_related("member"), many=True
        ).data

    def get_payroll_runs(self, obj):
        return PayrollRunSerializer(obj.payroll_runs.all()[:50], many=True).data

    def get_transactions(self, obj):
        return StructureTxSerializer(
            obj.transactions.select_related("member").all()[:100], many=True
        ).data
