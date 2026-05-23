from django.contrib import admin

from .models import (
    ClassicSavingsAccount,
    ClassicSavingsConfig,
    ClassicSavingsTransaction,
    SavingsAccount,
    SavingsTransaction,
)


@admin.register(SavingsAccount)
class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = ("member", "solde", "date_ouverture", "taux_interet_applique")
    search_fields = ("member__numero_membre", "member__nom", "member__prenom")
    autocomplete_fields = ("member",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(SavingsTransaction)
class SavingsTransactionAdmin(admin.ModelAdmin):
    list_display = ("account", "type_op", "montant", "solde_apres", "date")
    list_filter = ("type_op", "date")
    search_fields = ("account__member__numero_membre",)
    autocomplete_fields = ("account", "payment")
    date_hierarchy = "date"


# ── Épargne classique (dissociée de la cotisation) ──────────────────────────


@admin.register(ClassicSavingsConfig)
class ClassicSavingsConfigAdmin(admin.ModelAdmin):
    list_display = (
        "libelle",
        "actif",
        "taux_interet_mensuel",
        "depot_min",
        "depot_max",
        "retrait_validation_requise",
    )
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        # Singleton : pas de création multiple via l'admin.
        return not ClassicSavingsConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ClassicSavingsAccount)
class ClassicSavingsAccountAdmin(admin.ModelAdmin):
    list_display = ("member", "solde", "date_ouverture")
    search_fields = ("member__numero_membre", "member__nom", "member__prenom")
    autocomplete_fields = ("member",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClassicSavingsTransaction)
class ClassicSavingsTransactionAdmin(admin.ModelAdmin):
    list_display = ("account", "type_op", "montant", "solde_apres", "date")
    list_filter = ("type_op", "date")
    search_fields = ("account__member__numero_membre",)
    autocomplete_fields = ("account", "payment")
    date_hierarchy = "date"
