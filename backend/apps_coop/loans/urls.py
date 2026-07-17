"""Loans API — member-facing endpoints (UC3 step A).

Admin endpoints (instruct / decide / counter / disburse) will land here when
the Next.js admin dashboard is built. Until then, staff use ``/django-admin/``.
"""
from django.urls import path

from .avaliste_views import (
    avaliste_mandat_detail,
    avaliste_mandat_respond,
    avaliste_mandats_list,
)
from .lender_admin_views import (
    admin_compose_funding_manual,
    admin_lender_pool_summary,
    admin_list_lender_tranches,
)
from .judicial_admin import (
    admin_escalation_classer,
    admin_escalation_decision,
    admin_escalation_detail,
    admin_escalation_execution,
    admin_list_escalations,
    admin_open_escalation,
)
from .microcampaign_admin import (
    admin_campaign_application_decide,
    admin_campaign_applications,
    admin_campaign_close,
    admin_campaign_detail,
    admin_campaign_targeted_add,
    admin_campaign_targeted_remove,
    admin_campaigns,
    admin_loan_request_campaign_decide,
)
from .microcampaign_public import (
    public_active_campaigns,
    public_campaign_apply,
    public_campaign_detail,
)
from .views import (
    admin_list_installments,
    admin_list_loan_requests,
    admin_list_loan_renewals,
    admin_list_loans,
    admin_loan_detail,
    loan_disburse,
    loan_disburse_now,
    loan_disbursement_status,
    loan_eligibility,
    loan_extend_deadline,
    loan_request_evaluate_guarantee,
    loan_notice,
    loan_renewal_decide,
    loan_renewal_request,
    loan_request_create,
    loan_request_decide,
    loan_request_decide_provisional,
    loan_request_field_visit,
    loan_repay_from_savings,
    loan_request_list,
    loan_request_pay_study_fee_from_savings,
    loan_request_record_study_fee,
    loan_request_note,
    loan_request_upload_attachment,
    loans_me_active,
    transfer_available,
    loans_me_closed,
    me_lender_payouts,
)


app_name = "coop_loans"

urlpatterns = [
    # Member-facing
    path("me/eligibility/", loan_eligibility, name="eligibility"),
    path("me/requests/", loan_request_list, name="my-requests"),
    path("me/active/", loans_me_active, name="my-active-loans"),
    path("transfer/available/", transfer_available, name="transfer-available"),
    path(
        "me/loans/<int:pk>/repay-from-savings/",
        loan_repay_from_savings,
        name="loan-repay-from-savings",
    ),
    # P3 . Historique credits cloturees (parite portail web).
    path("me/closed/", loans_me_closed, name="my-closed-loans"),
    # CH-12 — Versements d'intérêts reçus en tant que prêteur.
    path("me/lender-payouts/", me_lender_payouts, name="my-lender-payouts"),
    # LOT 11 — Liste publique des campagnes micro-crédit actives (mobile +
    # vitrine). Pas d'auth : un membre peut partager le flyer en externe.
    path("campaigns/active/", public_active_campaigns, name="public-active-campaigns"),
    path("campaigns/<int:pk>/", public_campaign_detail, name="public-campaign-detail"),
    path("campaigns/<int:pk>/apply/", public_campaign_apply, name="public-campaign-apply"),
    path("requests/", loan_request_create, name="create-request"),
    # CH-5 — Upload de fichier rattaché à un LoanRequest (CGA, CFP, CNI, etc.).
    path(
        "requests/<int:pk>/attachments/",
        loan_request_upload_attachment,
        name="upload-loan-request-attachment",
    ),
    # Refonte 2026 — LOT 18 : mandats d'avaliste côté membre.
    path(
        "me/avaliste-mandats/",
        avaliste_mandats_list,
        name="my-avaliste-mandats",
    ),
    path(
        "me/avaliste-mandats/<int:pk>/",
        avaliste_mandat_detail,
        name="my-avaliste-mandat-detail",
    ),
    path(
        "me/avaliste-mandats/<int:pk>/respond/",
        avaliste_mandat_respond,
        name="my-avaliste-mandat-respond",
    ),
    # Reconduction (renewal) — membre actif
    path("<int:pk>/renewal/", loan_renewal_request, name="renewal-request"),
    # Admin/comité
    path("admin/requests/", admin_list_loan_requests, name="admin-list-requests"),
    path("admin/list/", admin_list_loans, name="admin-list-loans"),
    # A1 . Detail credit (echeances + remboursements) pour drawer admin.
    path(
        "admin/<int:pk>/detail/",
        admin_loan_detail,
        name="admin-loan-detail",
    ),
    # A2 . Liste echeances filtrables pour widget "Suivi paiement" dashboard.
    path(
        "admin/installments/",
        admin_list_installments,
        name="admin-list-installments",
    ),
    path("requests/<int:pk>/decide/", loan_request_decide, name="decide-request"),
    # CH-6 — Double approbation (provisoire → visite terrain → définitive).
    path(
        "requests/<int:pk>/decide-provisional/",
        loan_request_decide_provisional,
        name="decide-provisional",
    ),
    path(
        "requests/<int:pk>/field-visit/",
        loan_request_field_visit,
        name="field-visit",
    ),
    path(
        "requests/<int:pk>/study-fee/",
        loan_request_record_study_fee,
        name="record-study-fee",
    ),
    # Porte des frais 2026 — 3e canal : le membre règle sur son épargne.
    path(
        "requests/<int:pk>/study-fee/from-savings/",
        loan_request_pay_study_fee_from_savings,
        name="study-fee-from-savings",
    ),
    # L4 — Évaluation garantie matérielle par la commission (staff).
    path(
        "requests/<int:pk>/evaluate-guarantee/",
        loan_request_evaluate_guarantee,
        name="evaluate-guarantee",
    ),
    # Reconduction — admin : liste des demandes à décider + décision.
    path("admin/renewals/", admin_list_loan_renewals, name="admin-list-renewals"),
    path("renewals/<int:pk>/decide/", loan_renewal_decide, name="decide-renewal"),
    path("<int:pk>/disburse/", loan_disburse, name="disburse"),
    path("admin/<int:pk>/notice/", loan_notice, name="admin-notice"),
    # CH-8 — Extension de la date butoire d'un crédit actif/en_retard.
    path(
        "admin/<int:pk>/extend-deadline/",
        loan_extend_deadline,
        name="admin-extend-deadline",
    ),
    # CH-9 — Note de demande PDF (membre + admin).
    path(
        "requests/<int:pk>/note/",
        loan_request_note,
        name="loan-request-note",
    ),
    # CH-9 — Payer maintenant (auto-fill depuis moyen_reception).
    path(
        "admin/<int:pk>/disburse-now/",
        loan_disburse_now,
        name="admin-disburse-now",
    ),
    # CH-9 — Monitor du statut décaissement.
    path(
        "admin/<int:pk>/disbursement-status/",
        loan_disbursement_status,
        name="admin-disbursement-status",
    ),
    # Refonte 2026 — LOT 16 : admin CRUD MicrocreditCampaign + décision LR
    path("admin/campaigns/", admin_campaigns, name="admin-campaigns"),
    path("admin/campaigns/<int:pk>/", admin_campaign_detail, name="admin-campaign-detail"),
    path("admin/campaigns/<int:pk>/close/", admin_campaign_close, name="admin-campaign-close"),
    path(
        "admin/campaigns/<int:pk>/applications/",
        admin_campaign_applications,
        name="admin-campaign-applications",
    ),
    path(
        "admin/campaign-applications/<int:pk>/decide/",
        admin_campaign_application_decide,
        name="admin-campaign-application-decide",
    ),
    path(
        "admin/campaigns/<int:pk>/targeted/",
        admin_campaign_targeted_add,
        name="admin-campaign-targeted-add",
    ),
    path(
        "admin/campaigns/<int:pk>/targeted/<int:member_id>/",
        admin_campaign_targeted_remove,
        name="admin-campaign-targeted-remove",
    ),
    path(
        "admin/requests/<int:pk>/campaign-decide/",
        admin_loan_request_campaign_decide,
        name="admin-campaign-decide",
    ),
    # LA-1..3 . Pool tranches preteur (admin pilote le funding manuel).
    path(
        "admin/lender-tranches/",
        admin_list_lender_tranches,
        name="admin-lender-tranches",
    ),
    path(
        "admin/lender-tranches/summary/",
        admin_lender_pool_summary,
        name="admin-lender-pool-summary",
    ),
    path(
        "admin/<int:pk>/funding-manual/",
        admin_compose_funding_manual,
        name="admin-funding-manual",
    ),
    # Refonte 2026 — LOT 17 : escalades judiciaires phase D/E
    path("admin/escalations/", admin_list_escalations, name="admin-escalations"),
    path(
        "admin/escalations/<int:pk>/",
        admin_escalation_detail,
        name="admin-escalation-detail",
    ),
    path(
        "admin/loans/<int:loan_id>/escalation/",
        admin_open_escalation,
        name="admin-open-escalation",
    ),
    path(
        "admin/escalations/<int:pk>/decision/",
        admin_escalation_decision,
        name="admin-escalation-decision",
    ),
    path(
        "admin/escalations/<int:pk>/execution/",
        admin_escalation_execution,
        name="admin-escalation-execution",
    ),
    path(
        "admin/escalations/<int:pk>/classer/",
        admin_escalation_classer,
        name="admin-escalation-classer",
    ),
]
