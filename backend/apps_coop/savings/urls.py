"""Savings API.

  - GET /api/v1/savings/me/    → member's account snapshot (balance + recent tx)
  - GET /api/v1/savings/info/  → règles publiques (cut-off, lieu, taux)

Dépôts/retraits transitent par /api/v1/payments/init/ (cf. apps_coop.payments).
"""
from django.urls import path

from . import views
from .lender_views import (
    lender_add_tranche,
    lender_funding_respond,
    lender_me,
    lender_opt_in,
    lender_revoke,
)
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
    # Épargne classique (dissociée de la cotisation) — dépôt via /payments/init/
    path("classic/me/", views.classic_savings_me, name="classic-me"),
    path(
        "classic/transactions/",
        views.ClassicSavingsTransactionListView.as_view(),
        name="classic-transactions",
    ),
    path("classic/config/", views.classic_savings_config, name="classic-config"),
    # Relevé PDF des écritures du carnet (membre courant).
    path("me/ledger/", views.my_booklet_ledger_pdf, name="my-booklet-ledger"),
    # LOT 7-admin (refonte 2026) — Renouvellements épargne classique.
    path("admin/renewals/", views.admin_list_renewals, name="admin-renewals-list"),
    path(
        "admin/renewals/<int:pk>/process/",
        views.admin_process_renewal,
        name="admin-renewal-process",
    ),
    # Admin — déclenchement manuel du cron intérêts mensuel (recette).
    path(
        "admin/cron/monthly-interest/",
        views.admin_run_monthly_interest,
        name="admin-cron-monthly-interest",
    ),
    # Admin — reprise d'historique des carnets papier (antidaté).
    path(
        "admin/antidated-booklet/",
        views.admin_create_antidated_booklet,
        name="admin-antidated-booklet",
    ),
    path(
        "admin/antidated-entry/",
        views.admin_record_antidated_entry,
        name="admin-antidated-entry",
    ),
    # LOT 19 (refonte 2026) — Espace prêteur (consent + tranches + funding 24h).
    path("me/lender/", lender_me, name="lender-me"),
    path("me/lender/opt-in/", lender_opt_in, name="lender-opt-in"),
    path("me/lender/revoke/", lender_revoke, name="lender-revoke"),
    path("me/lender/tranches/", lender_add_tranche, name="lender-add-tranche"),
    # Récupération de tranche = ADMIN uniquement (le membre est seulement
    # notifié). Pas d'endpoint membre de cancel.
    path(
        "me/lender/funding-requests/<int:pk>/respond/",
        lender_funding_respond,
        name="lender-funding-respond",
    ),
]
