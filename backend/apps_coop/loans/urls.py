"""Loans API — member-facing endpoints (UC3 step A).

Admin endpoints (instruct / decide / counter / disburse) will land here when
the Next.js admin dashboard is built. Until then, staff use ``/django-admin/``.
"""
from django.urls import path

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
    # Reconduction (renewal) — membre actif
    path("<int:pk>/renewal/", loan_renewal_request, name="renewal-request"),
    # Admin/comité
    path("admin/requests/", admin_list_loan_requests, name="admin-list-requests"),
    path("admin/list/", admin_list_loans, name="admin-list-loans"),
    path("requests/<int:pk>/decide/", loan_request_decide, name="decide-request"),
    path("renewals/<int:pk>/decide/", loan_renewal_decide, name="decide-renewal"),
    path("<int:pk>/disburse/", loan_disburse, name="disburse"),
    path("admin/<int:pk>/notice/", loan_notice, name="admin-notice"),
]
