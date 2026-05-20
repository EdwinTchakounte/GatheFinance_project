"""Savings API.

  - GET /api/v1/savings/me/    → member's account snapshot (balance + recent tx)
  - GET /api/v1/savings/info/  → règles publiques (cut-off, lieu, taux)

Dépôts/retraits transitent par /api/v1/payments/init/ (cf. apps_coop.payments).
"""
from django.urls import path

from . import views
from .views import (
    SavingsAccountMeView,
    SavingsInfoView,
    SavingsTransactionListView,
)


app_name = "coop_savings"

urlpatterns = [
    path("me/", SavingsAccountMeView.as_view(), name="me"),
    path("info/", SavingsInfoView.as_view(), name="info"),
    path("transactions/", SavingsTransactionListView.as_view(), name="transactions"),
    # Retrait d'épargne (membre)
    path("withdrawal/", views.request_withdrawal_view, name="withdrawal-create"),
    path("withdrawals/me/", views.my_withdrawals, name="withdrawals-me"),
]
