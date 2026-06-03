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
from .judicial_admin import (
    admin_escalation_classer,
    admin_escalation_decision,
    admin_escalation_detail,
    admin_escalation_execution,
    admin_list_escalations,
    admin_open_escalation,
)
from .microcampaign_admin import (
    admin_campaign_close,
    admin_campaign_detail,
    admin_campaign_targeted_add,
    admin_campaign_targeted_remove,
    admin_campaigns,
    admin_loan_request_campaign_decide,
)
from .views import (
    admin_list_loan_requests,
    admin_list_loans,
    loan_disburse,
    loan_eligibility,
    loan_notice,
    loan_renewal_decide,
    loan_renewal_request,
    loan_request_create,
    loan_request_decide,
    loan_request_list,
    loans_me_active,
)


app_name = "coop_loans"

urlpatterns = [
    # Member-facing
    path("me/eligibility/", loan_eligibility, name="eligibility"),
    path("me/requests/", loan_request_list, name="my-requests"),
    path("me/active/", loans_me_active, name="my-active-loans"),
    path("requests/", loan_request_create, name="create-request"),
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
    path("requests/<int:pk>/decide/", loan_request_decide, name="decide-request"),
    path("renewals/<int:pk>/decide/", loan_renewal_decide, name="decide-renewal"),
    path("<int:pk>/disburse/", loan_disburse, name="disburse"),
    path("admin/<int:pk>/notice/", loan_notice, name="admin-notice"),
    # Refonte 2026 — LOT 16 : admin CRUD MicrocreditCampaign + décision LR
    path("admin/campaigns/", admin_campaigns, name="admin-campaigns"),
    path("admin/campaigns/<int:pk>/", admin_campaign_detail, name="admin-campaign-detail"),
    path("admin/campaigns/<int:pk>/close/", admin_campaign_close, name="admin-campaign-close"),
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
