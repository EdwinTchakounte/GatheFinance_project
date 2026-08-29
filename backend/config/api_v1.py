"""Mount point for the cooperative business API (`/api/v1/`).

Each domain app exposes its own `urls.py`; this file just bolts them together.
Kept separate from `config/urls.py` so the CMS side and the business side stay
visually distinct in the URL map.
"""
from django.urls import include, path

from apps_coop.savings import views as savings_views


urlpatterns = [
    # Members + auth (csrf / login / logout / me)
    path("", include("apps_coop.members.urls")),
    path("savings/", include("apps_coop.savings.urls")),
    # Admin — demandes de retrait (staff)
    path("admin/withdrawals/", savings_views.admin_list_withdrawals, name="admin-withdrawals-list"),
    path("admin/withdrawals/<int:pk>/decide/", savings_views.admin_decide_withdrawal, name="admin-withdrawals-decide"),
    path("admin/withdrawals/<int:pk>/mark-paid/", savings_views.admin_mark_withdrawal_paid, name="admin-withdrawals-mark-paid"),
    path("admin/withdrawals/<int:pk>/retry-payout/", savings_views.admin_retry_withdrawal_payout, name="admin-withdrawals-retry-payout"),
    path("loans/", include("apps_coop.loans.urls")),
    path("payments/", include("apps_coop.payments.urls")),
    path("notifications/", include("apps_coop.notifications.urls")),
    path("audit/", include("apps_coop.audit.urls")),
    # CH-4 — Moteur de formulaires dynamiques.
    path("forms/", include("apps_coop.forms.urls")),
    # Interactions sociales (likes + commentaires sur articles & campagnes).
    path("social/", include("apps_coop.social.urls")),
    # Support membre (messagerie fil unique membre ↔ support).
    path("support/", include("apps_coop.support.urls")),
    # Collectes particulières (caisse scolaire, tontine alimentaire).
    path("special-collections/", include("apps_coop.special_collections.urls")),
    path("structures/", include("apps_coop.structures.urls")),
    # Admin CMS — édition rapide des articles vitrine (image de couverture).
    path("cms/", include("apps_cms.cms.api_urls")),
]
