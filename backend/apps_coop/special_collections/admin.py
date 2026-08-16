from django.contrib import admin

from .models import SpecialCollectionMembership, SpecialCollectionTransaction


@admin.register(SpecialCollectionMembership)
class SpecialCollectionMembershipAdmin(admin.ModelAdmin):
    list_display = ("member", "type", "statut", "solde", "montant_cible", "created_at")
    list_filter = ("type", "statut")
    search_fields = ("member__numero_membre", "member__nom", "member__prenom")
    readonly_fields = ("solde", "validated_by", "validated_at")


@admin.register(SpecialCollectionTransaction)
class SpecialCollectionTransactionAdmin(admin.ModelAdmin):
    list_display = ("membership", "type_op", "montant", "solde_apres", "created_at")
    list_filter = ("type_op",)
    search_fields = ("membership__member__numero_membre",)
