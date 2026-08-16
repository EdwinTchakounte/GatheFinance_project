from django.contrib import admin

from .models import (
    SpecialCollectionCycle,
    SpecialCollectionMembership,
    SpecialCollectionTransaction,
)


@admin.register(SpecialCollectionCycle)
class SpecialCollectionCycleAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "statut", "date_debut", "date_fin", "closed_at")
    list_filter = ("type", "statut")
    search_fields = ("nom",)
    readonly_fields = ("closed_at", "closed_by", "created_by")


@admin.register(SpecialCollectionMembership)
class SpecialCollectionMembershipAdmin(admin.ModelAdmin):
    list_display = ("member", "type", "cycle", "statut", "solde", "montant_cible", "created_at")
    list_filter = ("type", "statut", "cycle")
    search_fields = ("member__numero_membre", "member__nom", "member__prenom")
    readonly_fields = ("solde", "validated_by", "validated_at")


@admin.register(SpecialCollectionTransaction)
class SpecialCollectionTransactionAdmin(admin.ModelAdmin):
    list_display = ("membership", "type_op", "montant", "solde_apres", "created_at")
    list_filter = ("type_op",)
    search_fields = ("membership__member__numero_membre",)
