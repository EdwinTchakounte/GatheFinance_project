"""Source unique de vérité pour les images d'illustration par défaut.

Quand un contenu (article blog, campagne micro-crédit) n'a pas d'image
uploadée par l'éditeur, on retourne une URL d'image stock Unsplash CDN
choisie selon des mots-clés du titre / profil.

Toutes les API (mobile, portail, admin) consomment ces URLs depuis le
même endpoint — pas de hardcoding côté client. L'éditeur peut toujours
override en uploadant une image dans Wagtail ou en attachant un flyer
à la campagne.
"""
from __future__ import annotations

# Mapping mot-clé -> URL Unsplash CDN. La 1re entrée qui matche dans le
# texte de référence (titre d'article ou nom+profil de campagne) gagne.
_ARTICLE_STOCK_MAP: list[tuple[tuple[str, ...], str]] = [
    (
        ("pme", "entreprise", "business", "commerce", "commerc"),
        "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("credit", "crédit", "prêt", "pret", "emprunt"),
        "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("immobilier", "maison", "logement", "propriete", "propriété"),
        "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("epargne", "épargne", "savings", "economie", "économie"),
        "https://images.unsplash.com/photo-1579621970795-87facc2f976d?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("education", "éducation", "enfant", "scolaire", "formation", "caisse scolaire"),
        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("agriculteur", "agricole", "agriculture", "ferme", "champ"),
        "https://images.unsplash.com/photo-1500651230702-0e2d8a49d4ad?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("cooperative", "coopérative", "coop", "communaut", "solidarit"),
        "https://images.unsplash.com/photo-1521791136064-7986c2920216?w=900&q=80&auto=format&fit=crop",
    ),
]

_ARTICLE_DEFAULT = (
    "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=900&q=80&auto=format&fit=crop"
)


_CAMPAIGN_STOCK_MAP: list[tuple[tuple[str, ...], str]] = [
    (
        ("commerc", "commercants", "commerçants", "boutique", "marche", "marché"),
        "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("parent", "scolaire", "rentree", "rentrée", "enfant"),
        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("agriculteur", "agricole", "ferme", "champ", "paysan"),
        "https://images.unsplash.com/photo-1500651230702-0e2d8a49d4ad?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("femme", "feminin", "féminin", "mama"),
        "https://images.unsplash.com/photo-1573164713988-8665fc963095?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("jeune", "startup", "innovation", "tech"),
        "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=900&q=80&auto=format&fit=crop",
    ),
    (
        ("artisan", "menuisier", "couture", "tisseur"),
        "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=900&q=80&auto=format&fit=crop",
    ),
]

_CAMPAIGN_DEFAULT = (
    "https://images.unsplash.com/photo-1565514020179-026b92b84bb6?w=900&q=80&auto=format&fit=crop"
)


def _match(haystack: str, mapping: list[tuple[tuple[str, ...], str]], default: str) -> str:
    """Lowercase contains pour chaque tuple de mots-clés. 1re entrée gagne."""
    lower = haystack.lower()
    for keywords, url in mapping:
        for kw in keywords:
            if kw in lower:
                return url
    return default


def article_image_for(title: str) -> str:
    """URL d'image stock pour un article sans cover uploadée."""
    return _match(title or "", _ARTICLE_STOCK_MAP, _ARTICLE_DEFAULT)


def campaign_image_for(nom: str, profil_cible: str = "") -> str:
    """URL d'image stock pour une campagne sans flyer uploadé."""
    return _match(f"{nom or ''} {profil_cible or ''}", _CAMPAIGN_STOCK_MAP, _CAMPAIGN_DEFAULT)
