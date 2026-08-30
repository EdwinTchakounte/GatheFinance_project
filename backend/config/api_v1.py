"""Mount point for the cooperative business API (`/api/v1/`).

Each domain app exposes its own `urls.py`; this file just bolts them together.
Kept separate from `config/urls.py` so the CMS side and the business side stay
visually distinct in the URL map.
"""
from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps_coop.savings import views as savings_views


@api_view(["GET"])
@permission_classes([AllowAny])
def app_version_view(request):
    """Version mobile minimale requise + dernière version + lien de mise à jour.

    Public (le gate de mise à jour doit fonctionner AVANT toute connexion).
    Tout est piloté par AppSetting (admin), sans redéploiement :
      - ``mobile.min_version``       : en-dessous → mise à jour OBLIGATOIRE (blocage)
      - ``mobile.latest_version``    : dernière version publiée (info)
      - ``mobile.android_download_url`` : URL de l'APK (bouton « Mettre à jour »)
      - ``mobile.update_message``    : message affiché sur l'écran de blocage
    """
    from apps_coop.audit.services import get_str_setting

    return Response(
        {
            "min_version": get_str_setting("mobile.min_version", "1.0.0"),
            "latest_version": get_str_setting("mobile.latest_version", "1.1.0"),
            "android_download_url": get_str_setting(
                "mobile.android_download_url",
                "https://app.gathe-finance.com/telecharger-app",
            ),
            "update_message": get_str_setting(
                "mobile.update_message",
                "Une nouvelle version de l'application est disponible. "
                "Merci de mettre à jour pour continuer.",
            ),
        }
    )


urlpatterns = [
    # Version mobile requise (gate de mise à jour) — public.
    path("app-version/", app_version_view, name="app-version"),
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
