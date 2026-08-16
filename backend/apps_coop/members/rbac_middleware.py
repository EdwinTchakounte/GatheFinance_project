"""Enforcement RBAC centralisé des endpoints *admin* (le « back » du front+back).

Plutôt que d'éditer les ~40 vues admin une à une, on garde une seule table de
correspondance *préfixe d'URL → ressource* et on la vérifie ici. Le sidebar
front masque déjà les onglets ; ce middleware empêche l'appel direct de l'API.

Sûreté : les comptes à **accès total** (superuser / groupe admin / staff-comité
*legacy* sans rôle) contournent totalement la vérification — donc l'existant
n'est jamais impacté. Seuls les comptes à rôle restreint (nouveaux) sont filtrés.

Un chemin admin non mappé est **refusé** pour un compte restreint (fail-closed) :
il ne devrait toucher que les ressources qui lui sont accordées.
"""
from __future__ import annotations

import re

from django.http import JsonResponse

from .access import has_full_access, staff_has_resource

API_PREFIX = "/api/v1/"

# Ordre : règles spécifiques AVANT les catch-all (`startswith`, 1er match gagne).
# Préfixes exprimés APRÈS `/api/v1/`.
PREFIX_RULES: list[tuple[str, str]] = [
    ("admin/access/", "access"),
    ("admin/dashboard/", "dashboard"),
    # Rapport PDF « état de la coopérative » = vue d'ensemble (dashboard).
    # AVANT admin/members/ pour ne pas être capté par ce préfixe.
    ("admin/report/", "dashboard"),
    ("admin/members/", "members"),
    ("admin/membership-requests/", "membership-requests"),
    ("admin/adhesions/", "adhesions"),
    ("admin/brc/", "brc"),
    ("admin/booklet-orders/", "booklet-orders"),
    ("admin/withdrawals/", "withdrawals"),
    # Saisies antidatées — AVANT le catch-all savings/admin/ (1er match gagne),
    # sinon elles tomberaient sous la ressource « renewals ».
    ("savings/admin/antidated-booklet/", "antidated-entries"),
    ("savings/admin/antidated-entry/", "antidated-entries"),
    # Renouvellements épargne (app savings : renewals + cron intérêt mensuel).
    ("savings/admin/", "renewals"),
    # Crédit (app loans)
    ("loans/admin/campaigns/", "campaigns"),
    ("loans/admin/campaign-applications/", "campaigns"),
    ("loans/admin/escalations/", "escalations"),
    ("loans/admin/lender-tranches/", "lender-tranches"),
    ("loans/admin/renewals/", "loan-renewals"),
    ("loans/admin/avaliste-consents/", "avaliste"),
    ("loans/admin/requests/", "loan-requests"),
    ("loans/admin/loans/", "loans"),
    ("loans/admin/list/", "loans"),
    ("loans/admin/installments/", "loans"),
    ("loans/admin/", "loans"),  # catch-all (funding-manual/<id>/…)
    # Paiements / coûts
    ("payments/admin/cash-in/", "payments"),
    ("payments/admin/config/", "costs"),
    ("payments/admin/fees/", "costs"),
    ("payments/admin/rates/", "costs"),
    ("payments/admin/", "payments"),
    # Collectes particulières (caisse scolaire, tontine alimentaire)
    ("special-collections/admin/", "special-collections"),
    # Notifications / annonces
    ("notifications/admin/announcements/", "announcements"),
    # Audit / paramètres / cron / documents officiels
    ("audit/admin/logs/", "audit"),
    ("audit/admin/settings/", "app-settings"),
    ("audit/admin/cron-schedules/", "cron-schedules"),
    ("audit/admin/cooperative-asset/", "cooperative-asset"),
    # Formulaires dynamiques
    ("forms/admin/", "forms"),
    # Commentaires (modération)
    ("social/admin/comments/", "comments"),
    # Blog vitrine (CMS)
    ("cms/blog/", "blog"),
    ("cms/", "blog"),
]

_ADMIN_SEGMENT = re.compile(r"(^|/)admin/")

# Règles regex (vérifiées AVANT les préfixes) pour les cas à segment dynamique.
# Ouvrir une escalade se fait sur un crédit : `loans/admin/loans/<id>/escalation/`
# — sinon capté par le préfixe générique `loans/admin/loans/` → `loans`.
REGEX_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^loans/admin/loans/\d+/escalation/"), "escalations"),
]


def _resolve(rest: str) -> tuple[bool, str | None]:
    """(is_admin_endpoint, resource_key). ``rest`` = chemin après /api/v1/."""
    for pattern, resource in REGEX_RULES:
        if pattern.match(rest):
            return True, resource
    for prefix, resource in PREFIX_RULES:
        if rest.startswith(prefix):
            return True, resource
    # Non mappé : c'est quand même un endpoint admin s'il contient /admin/.
    if _ADMIN_SEGMENT.search(rest):
        return True, None
    return False, None


class RBACResourceMiddleware:
    """Bloque (403) l'accès direct aux endpoints admin hors ressources accordées."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        denied = self._check(request)
        if denied is not None:
            return denied
        return self.get_response(request)

    def _check(self, request):
        if request.method == "OPTIONS":
            return None
        path = request.path
        if not path.startswith(API_PREFIX):
            return None
        rest = path[len(API_PREFIX):]
        is_admin, resource = _resolve(rest)
        if not is_admin:
            return None

        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            # Laisser la vue renvoyer le 401/403 habituel (IsStaff).
            return None
        if has_full_access(user):
            return None
        # Compte restreint (rôles) : la ressource doit être explicitement accordée.
        if resource is not None and staff_has_resource(user, resource):
            return None
        return JsonResponse(
            {"detail": "Accès refusé : ressource non autorisée pour ce compte."},
            status=403,
        )
