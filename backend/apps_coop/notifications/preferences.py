"""Préférences de notification **push** par catégorie (opt-out).

Le mobile ne pilote plus que le canal *push*, réparti en 5 catégories
métier. Ce module fait le lien entre le ``type`` libre d'une ``Notification``
(souvent le code d'un template email, ex. ``credit.approved``) et l'une des
catégories, puis décide si un push doit être envoyé pour un utilisateur donné.

Opt-out : par défaut tout est autorisé. Une catégorie n'est bloquée que si
l'utilisateur a explicitement mis ``false`` dans ses préférences. Un ``type``
non catégorisé (annonce, support, commentaire…) autorise toujours le push.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Les 5 catégories pilotables (miroir de l'enum mobile NotifCategory).
PUSH_CATEGORIES = ["epargne", "credit", "carnet", "reconduction", "securite"]

# Mots-clés → catégorie. Robuste aux variantes de codes (fr/en).
_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("carnet", ("carnet", "booklet")),
    ("reconduction", ("reconduction", "renewal", "renouvel")),
    (
        "credit",
        ("credit", "crédit", "loan", "pret", "prêt", "echeance", "échéance",
         "decaiss", "décaiss", "comite", "comité", "funding", "lender",
         "remboursement", "avaliste", "garantie"),
    ),
    (
        "epargne",
        ("epargne", "épargne", "saving", "depot", "dépôt", "deposit",
         "interet", "intérêt", "solde", "collecte", "cotisation", "placement",
         "versement", "payment", "recu", "reçu"),
    ),
    (
        "securite",
        ("securite", "sécurité", "security", "password", "mot_de_passe",
         "login", "connexion", "pin", "access", "acces", "accès"),
    ),
]


def category_for_type(notif_type: str | None) -> str | None:
    """Catégorie push d'un ``type`` de notification, ou ``None`` si non classé."""
    t = (notif_type or "").lower()
    if not t:
        return None
    for category, keywords in _KEYWORDS:
        if any(k in t for k in keywords):
            return category
    return None


def get_push_categories(user) -> dict[str, bool]:
    """Map complète { catégorie: bool } pour ``user`` (défauts = tout activé)."""
    stored: dict = {}
    try:
        pref = getattr(user, "notification_preference", None)
        if pref is not None and isinstance(pref.push_categories, dict):
            stored = pref.push_categories
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning("lecture préférences push impossible", exc_info=True)
    return {c: bool(stored.get(c, True)) for c in PUSH_CATEGORIES}


def push_allowed(user, notif_type: str | None) -> bool:
    """True si un push pour ``notif_type`` est autorisé pour ``user``.

    Opt-out : autorisé sauf si la catégorie correspondante est explicitement
    désactivée. Un type non catégorisé est toujours autorisé.
    """
    category = category_for_type(notif_type)
    if category is None:
        return True
    return get_push_categories(user).get(category, True)


def set_push_categories(user, updates: dict) -> dict[str, bool]:
    """Fusionne ``updates`` (partiel) dans les préférences de ``user``.

    Ne conserve que les catégories connues et les valeurs booléennes.
    Retourne la map complète résultante.
    """
    from .models import NotificationPreference

    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    current = pref.push_categories if isinstance(pref.push_categories, dict) else {}
    merged = dict(current)
    for key, value in (updates or {}).items():
        if key in PUSH_CATEGORIES:
            merged[key] = bool(value)
    pref.push_categories = merged
    pref.save()
    return {c: bool(merged.get(c, True)) for c in PUSH_CATEGORIES}
