"""Payments API routes.

Mounted under ``/api/v1/payments/`` by ``config/api_v1.py``.
"""
from django.urls import path

from . import views


app_name = "coop_payments"

urlpatterns = [
    path("init/", views.init_payment, name="init"),
    path("me/", views.payments_me, name="me"),
    path("fees/", views.list_fees, name="fees"),
    path("rates/", views.list_rates, name="rates"),
    path("webhook/tara/", views.webhook_tara, name="webhook-tara"),
    # Dev-only simulator — returns 404 when DEBUG=False. Kept inline rather
    # than gated by URL config so the route map stays simple.
    path("dev/<int:pk>/confirm/", views.dev_confirm_payment, name="dev-confirm"),
    # Admin (staff-only)
    path("admin/", views.admin_list_payments, name="admin-list"),
    # B1 . Saisie versement agence (cash-in) par admin.
    path("admin/cash-in/", views.admin_cash_in_payment, name="admin-cash-in"),
    path(
        "admin/<int:pk>/invalidate/",
        views.admin_invalidate_payment,
        name="admin-invalidate",
    ),
    # Édition des coûts modifiables — frais + taux (BR2)
    path("admin/config/", views.admin_config, name="admin-config"),
    path("admin/fees/<str:code>/", views.admin_update_fee, name="admin-update-fee"),
    path("admin/rates/<str:code>/", views.admin_update_rate, name="admin-update-rate"),
    path(
        "admin/transaction-fee-operations/",
        views.admin_update_transaction_fee_operations,
        name="admin-update-transaction-fee-operations",
    ),
    path(
        "admin/transaction-fee-payin-types/",
        views.admin_update_transaction_fee_payin_types,
        name="admin-update-transaction-fee-payin-types",
    ),
    # Reçu de versement (mini-facture PDF) — membre propriétaire ou admin.
    path("<int:pk>/receipt/", views.payment_receipt, name="receipt"),
    path("<int:pk>/", views.payment_detail, name="detail"),
]
