"""Registre canonique des *ressources* de l'admin (RBAC).

Une ressource = un onglet du tableau de bord admin. C'est la source de vérité
partagée entre :
  * l'enforcement backend (permission ``ResourceAccess``),
  * l'UI admin (filtrage du sidebar + cases à cocher des rôles),
  * la définition des ``StaffRole``.

Les clés DOIVENT rester alignées avec le ``href`` des entrées du sidebar
(`frontend/apps/admin/src/components/sidebar.tsx`) — sans le slash initial.
"""
from __future__ import annotations


# (key, label) — l'ordre suit le sidebar admin.
ADMIN_RESOURCES: list[tuple[str, str]] = [
    ("dashboard", "Vue d'ensemble"),
    ("adhesions", "Pipeline adhésion"),
    ("membership-requests", "Adhésions"),
    ("loan-requests", "Demandes de crédit"),
    ("loans", "Crédits"),
    ("loan-renewals", "Reconductions"),
    ("lender-tranches", "Pool prêteurs"),
    ("payments", "Paiements"),
    ("withdrawals", "Retraits épargne"),
    ("booklet-orders", "Commandes carnet"),
    ("antidated-entries", "Saisies antidatées"),
    ("collecte-preferences", "Fin de mois collecte"),
    ("members", "Membres"),
    ("brc", "Justificatifs BRC"),
    ("renewals", "Renouvellements épargne"),
    ("campaigns", "Campagnes micro-crédit"),
    ("escalations", "Escalades judiciaires"),
    ("costs", "Coûts"),
    ("app-settings", "Paramètres"),
    ("cron-schedules", "Planification (cron)"),
    ("cooperative-asset", "Documents officiels"),
    ("announcements", "Annonces"),
    ("blog", "Articles vitrine"),
    ("forms", "Formulaires"),
    ("audit", "Journal d'audit"),
    ("comments", "Commentaires"),
    ("support", "Support membres"),
    ("access", "Utilisateurs & accès"),
]

RESOURCE_KEYS: frozenset[str] = frozenset(k for k, _ in ADMIN_RESOURCES)


def valid_resources(keys) -> list[str]:
    """Filtre + dédoublonne une liste de clés en gardant l'ordre du registre."""
    wanted = set(keys or [])
    return [k for k, _ in ADMIN_RESOURCES if k in wanted]


def resources_payload() -> list[dict[str, str]]:
    """Représentation JSON du registre pour le frontend."""
    return [{"key": k, "label": label} for k, label in ADMIN_RESOURCES]
