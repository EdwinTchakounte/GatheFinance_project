"""Payments API routes.

Mounted under ``/api/v1/payments/`` by ``config/api_v1.py``.
"""
from django.urls import path

from . import views


app_name = "coop_payments"

urlpatterns = [
    path("init/", views.init_payment, name="init"),
    path("fees/", views.list_fees, name="fees"),
    path("webhook/tara/", views.webhook_tara, name="webhook-tara"),
    # Dev-only simulator — returns 404 when DEBUG=False. Kept inline rather
    # than gated by URL config so the route map stays simple.
    path("dev/<int:pk>/confirm/", views.dev_confirm_payment, name="dev-confirm"),
    # Admin (staff-only)
    path("admin/", views.admin_list_payments, name="admin-list"),
    path("<int:pk>/", views.payment_detail, name="detail"),
]
