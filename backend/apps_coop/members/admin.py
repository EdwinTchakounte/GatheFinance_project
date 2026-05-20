"""Django admin for the members domain.

The ``MembershipRequest`` admin is the **operational workflow** for UC1:
staff opens a pending request, optionally edits the identity fields, then
clicks "Approuver la demande" (object-level button) or selects rows and runs
the bulk action. Both paths delegate to ``services.approve_membership_request``
which creates the User + Member + SavingsAccount atomically.
"""
from __future__ import annotations

from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from . import services
from .models import BookletOrder, Document, Member, MembershipRequest


# ---------------------------------------------------------------------------
# Member
# ---------------------------------------------------------------------------


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("numero_membre", "prenom", "nom", "statut", "date_adhesion", "phone")
    list_filter = ("statut", "date_adhesion")
    search_fields = ("numero_membre", "prenom", "nom", "user__email", "phone")
    autocomplete_fields = ("user",)
    date_hierarchy = "date_adhesion"


# ---------------------------------------------------------------------------
# MembershipRequest — the UC1 operational surface
# ---------------------------------------------------------------------------


@admin.action(description="Approuver les demandes sélectionnées (création membre + compte épargne)")
def bulk_approve(modeladmin, request, queryset):
    """Bulk-approve action used from the changelist's actions dropdown.

    Only requests in ``en_attente`` are processed; others are skipped with a
    warning so the operator sees what happened.
    """
    ok, skipped, errored = 0, 0, 0
    for req in queryset:
        if req.statut != MembershipRequest.Statut.EN_ATTENTE:
            skipped += 1
            continue
        try:
            services.approve_membership_request(req, instructed_by=request.user)
            ok += 1
        except ValueError as exc:
            errored += 1
            messages.error(request, f"Demande #{req.pk}: {exc}")
    messages.success(
        request,
        f"Adhésion : {ok} approuvée(s), {skipped} ignorée(s), {errored} en erreur.",
    )


@admin.register(MembershipRequest)
class MembershipRequestAdmin(admin.ModelAdmin):
    list_display = (
        "display_name", "email", "phone", "city", "statut",
        "created_at", "instruit_par", "decision_links",
    )
    list_filter = ("statut", "language", "created_at")
    search_fields = ("nom", "prenom", "email", "phone", "city", "motivation")
    autocomplete_fields = ("instruit_par", "member")
    date_hierarchy = "created_at"
    readonly_fields = (
        "created_at", "updated_at", "date_decision",
        "ip_address", "user_agent", "member",
    )
    actions = [bulk_approve]

    fieldsets = (
        ("Identité saisie", {"fields": ("nom", "prenom", "email", "phone", "city", "language", "motivation")}),
        ("Workflow", {"fields": ("statut", "motif_rejet", "internal_notes")}),
        ("Décision", {"fields": ("instruit_par", "date_decision", "member")}),
        ("Traçabilité", {"fields": ("ip_address", "user_agent", "created_at", "updated_at")}),
    )

    @admin.display(description="Demandeur")
    def display_name(self, obj: MembershipRequest) -> str:
        return obj.display_name

    @admin.display(description="Actions")
    def decision_links(self, obj: MembershipRequest):
        if obj.statut != MembershipRequest.Statut.EN_ATTENTE:
            return obj.get_statut_display()
        return format_html(
            '<a class="button" href="{}">Approuver</a> &nbsp; '
            '<a class="button" style="background:#ba2121;color:#fff" href="{}">Rejeter</a>',
            f"./{obj.pk}/approve/",
            f"./{obj.pk}/reject/",
        )

    # --- Custom object-level URLs ----------------------------------------
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/approve/",
                self.admin_site.admin_view(self._approve_view),
                name="members_membershiprequest_approve",
            ),
            path(
                "<int:pk>/reject/",
                self.admin_site.admin_view(self._reject_view),
                name="members_membershiprequest_reject",
            ),
        ]
        return custom + urls

    def _approve_view(self, request, pk: int):
        req = self.get_object(request, pk)
        if req is None:
            messages.error(request, "Demande introuvable.")
            return redirect("..")
        if request.method == "POST":
            try:
                services.approve_membership_request(
                    req,
                    instructed_by=request.user,
                    prenom=request.POST.get("prenom"),
                    nom=request.POST.get("nom"),
                )
                messages.success(
                    request,
                    f"Demande approuvée : Member {req.member.numero_membre} créé.",
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("..")
        return render(
            request,
            "admin/members/approve_membership.html",
            {"request_obj": req, "title": f"Approuver la demande #{req.pk}"},
            using=None,
        )

    def _reject_view(self, request, pk: int):
        req = self.get_object(request, pk)
        if req is None:
            messages.error(request, "Demande introuvable.")
            return redirect("..")
        if request.method == "POST":
            try:
                services.reject_membership_request(
                    req,
                    instructed_by=request.user,
                    motif=request.POST.get("motif", ""),
                )
                messages.success(request, "Demande rejetée.")
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("..")
        return render(
            request,
            "admin/members/reject_membership.html",
            {"request_obj": req, "title": f"Rejeter la demande #{req.pk}"},
            using=None,
        )


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("nom_original", "type_doc", "member", "entite_liee_type", "created_at")
    list_filter = ("type_doc", "entite_liee_type")
    search_fields = ("nom_original", "member__numero_membre")
    autocomplete_fields = ("member",)


# ---------------------------------------------------------------------------
# BookletOrder — l'agence suit l'impression et la délivrance ici
# ---------------------------------------------------------------------------


@admin.register(BookletOrder)
class BookletOrderAdmin(admin.ModelAdmin):
    list_display = ("member", "statut", "created_at", "date_impression", "date_delivrance")
    list_filter = ("statut", "created_at")
    search_fields = ("member__numero_membre", "member__nom", "member__prenom")
    autocomplete_fields = ("member", "payment")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Commande", {"fields": ("member", "payment", "statut")}),
        ("Suivi agence", {"fields": ("date_impression", "date_delivrance", "notes_agence")}),
        ("Métadonnées", {"fields": ("created_at", "updated_at")}),
    )
