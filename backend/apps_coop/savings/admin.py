from django.contrib import admin

from .models import SavingsAccount, SavingsTransaction


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
