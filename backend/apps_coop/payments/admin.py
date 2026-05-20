from django.contrib import admin

from .models import FeeType, Payment, PaymentProof


class PaymentProofInline(admin.TabularInline):
    model = PaymentProof
    extra = 0


@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "montant", "actif")
    list_filter = ("actif",)
    search_fields = ("code", "libelle")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "member", "type", "source", "montant", "statut",
        "date_versement", "provider_code", "reference_externe",
    )
    list_filter = ("statut", "source", "type", "date_versement", "provider_code")
    search_fields = (
        "id", "reference_externe", "member__numero_membre",
        "member__nom", "member__prenom",
    )
    autocomplete_fields = ("member", "loan", "loan_installment", "validated_by")
    readonly_fields = ("idempotency_key", "created_at", "updated_at", "gateway_initiated_at")
    date_hierarchy = "date_versement"
    inlines = [PaymentProofInline]


@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):
    list_display = ("payment", "type_document", "taille", "created_at")
    autocomplete_fields = ("payment",)
    list_filter = ("type_document",)
