"""Django admin for the loans domain.

The ``LoanRequest`` admin is the **operational surface** for the credit
committee: when a request is in ``en_instruction``, custom buttons let the
president record the comité's decision (approve or reject). Approving a
request creates the ``Loan`` + the full ``LoanInstallment`` schedule in a
single atomic transaction — see ``services.approve_loan_request``.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import date

from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from . import services
from .models import Loan, LoanGuarantee, LoanInstallment, LoanRenewal, LoanRepayment, LoanRequest


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class LoanGuaranteeInline(admin.TabularInline):
    model = LoanGuarantee
    extra = 0


class LoanInstallmentInline(admin.TabularInline):
    model = LoanInstallment
    extra = 0
    can_delete = False
    readonly_fields = ("numero_echeance", "date_echeance", "montant_capital", "montant_interets", "montant_total", "montant_paye", "statut")
    ordering = ("numero_echeance",)


# ---------------------------------------------------------------------------
# LoanRequest — comité workflow
# ---------------------------------------------------------------------------


@admin.register(LoanRequest)
class LoanRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "member",
        "montant_demande",
        "duree_mois",
        "statut",
        "date_soumission",
        "decision_links",
    )
    list_filter = ("statut", "date_soumission")
    search_fields = ("member__numero_membre", "member__nom", "motif")
    autocomplete_fields = ("member", "instruit_par", "decide_par", "pv_comite")
    date_hierarchy = "date_soumission"
    readonly_fields = ("date_soumission", "date_decision", "date_comite")
    fieldsets = (
        ("Demande", {"fields": ("member", "montant_demande", "duree_mois", "motif")}),
        ("Instruction (agent staff)", {"fields": ("instruit_par", "avis_instruction", "scoring")}),
        ("Décision (président comité)", {"fields": ("statut", "motif_rejet", "decide_par", "date_decision", "date_comite", "pv_comite")}),
        ("Contre-proposition", {"fields": ("montant_revise", "duree_revisee")}),
    )

    @admin.display(description="Actions")
    def decision_links(self, obj: LoanRequest):
        if obj.statut != LoanRequest.Statut.EN_INSTRUCTION:
            return obj.get_statut_display()
        return format_html(
            '<a class="button" href="{}">Approuver</a> &nbsp; '
            '<a class="button" style="background:#ba2121;color:#fff" href="{}">Rejeter</a>',
            f"./{obj.pk}/approve/",
            f"./{obj.pk}/reject/",
        )

    # ---- Custom URLs ------------------------------------------------------
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/approve/",
                self.admin_site.admin_view(self._approve_view),
                name="loans_loanrequest_approve",
            ),
            path(
                "<int:pk>/reject/",
                self.admin_site.admin_view(self._reject_view),
                name="loans_loanrequest_reject",
            ),
        ]
        return custom + urls

    # ---- Approve ---------------------------------------------------------
    def _approve_view(self, request, pk: int):
        obj = self.get_object(request, pk)
        if obj is None:
            messages.error(request, "Demande introuvable.")
            return redirect("..")
        if request.method == "POST":
            try:
                taux = Decimal(request.POST.get("taux_interet", "").strip().replace(",", "."))
                duree_premiere = request.POST.get("date_premiere_echeance", "").strip()
                if not duree_premiere:
                    raise ValueError("La date de la 1re échéance est requise.")
                date_premiere = date.fromisoformat(duree_premiere)
                loan = services.approve_loan_request(
                    obj,
                    decided_by=request.user,
                    taux_annuel=taux,
                    date_premiere_echeance=date_premiere,
                    date_comite=date.today(),
                )
                messages.success(
                    request,
                    f"Demande approuvée : Loan {loan.numero_dossier} créé avec "
                    f"{loan.duree_mois} échéances.",
                )
            except (ValueError, InvalidOperation) as exc:
                messages.error(request, str(exc))
            return redirect("..")
        return render(
            request,
            "admin/loans/approve_loan_request.html",
            {
                "request_obj": obj,
                "title": f"Approuver la demande #{obj.pk}",
                "default_date_premiere": date.today().isoformat(),
            },
        )

    # ---- Reject ----------------------------------------------------------
    def _reject_view(self, request, pk: int):
        obj = self.get_object(request, pk)
        if obj is None:
            messages.error(request, "Demande introuvable.")
            return redirect("..")
        if request.method == "POST":
            try:
                services.reject_loan_request(
                    obj,
                    decided_by=request.user,
                    motif=request.POST.get("motif", ""),
                )
                messages.success(request, "Demande rejetée.")
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("..")
        return render(
            request,
            "admin/loans/reject_loan_request.html",
            {"request_obj": obj, "title": f"Rejeter la demande #{obj.pk}"},
        )


# ---------------------------------------------------------------------------
# Loan / installments / repayments / renewals — standard admin
# ---------------------------------------------------------------------------


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("numero_dossier", "member", "montant", "taux_interet", "duree_mois", "statut", "solde_restant", "date_decaissement")
    list_filter = ("statut", "date_decaissement")
    search_fields = ("numero_dossier", "member__numero_membre", "member__nom")
    autocomplete_fields = ("member", "loan_request")
    inlines = [LoanGuaranteeInline, LoanInstallmentInline]
    date_hierarchy = "date_decaissement"
    readonly_fields = ("created_at", "updated_at", "numero_dossier", "montant_total_du")


@admin.register(LoanInstallment)
class LoanInstallmentAdmin(admin.ModelAdmin):
    list_display = ("loan", "numero_echeance", "date_echeance", "montant_total", "montant_paye", "statut")
    list_filter = ("statut", "date_echeance")
    search_fields = ("loan__numero_dossier",)
    autocomplete_fields = ("loan",)


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ("installment", "payment", "montant_impute", "date")
    autocomplete_fields = ("installment", "payment")
    date_hierarchy = "date"


@admin.register(LoanRenewal)
class LoanRenewalAdmin(admin.ModelAdmin):
    list_display = ("loan", "nouvelle_duree_mois", "statut", "date_demande", "date_decision")
    list_filter = ("statut", "date_demande")
    autocomplete_fields = ("loan", "frais_reconduction_payment")
