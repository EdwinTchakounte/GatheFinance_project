"""Fenêtre du placement épargne classique (fermeture datée).

Le placement (sous-canal bloqué qui finance les crédits) FERME à une date-
limite : au-delà, tout nouveau versement d'épargne classique va en LIBRE et
l'ajout d'une tranche de placement est refusé. Les placements DÉJÀ existants ne
sont pas touchés — seuls les NOUVEAUX sont bloqués.

Décision client (2026-07-11) : fermeture au **1er août 2026**.

Deux verrous, tous deux tunables sans déploiement (AppSetting) :
  - ``epargne.placement.enabled``     : on/off global (défaut "true") ;
  - ``savings.placement.closed_from`` : date ISO de fermeture (défaut "2026-08-01").
"""
from __future__ import annotations

from datetime import date

PLACEMENT_CLOSED_FROM_DEFAULT = "2026-08-01"


def placement_open(on: date | None = None) -> bool:
    """True si le placement est encore ouvert à la date ``on`` (défaut : aujourd'hui).

    Fermé si le toggle global est off OU si ``on >= savings.placement.closed_from``.
    Ne lève jamais : une AppSetting mal formée retombe sur le défaut.
    """
    from apps_coop.audit.services import get_str_setting

    if get_str_setting("epargne.placement.enabled", "true").strip().lower() != "true":
        return False
    if on is None:
        from django.utils import timezone

        on = timezone.localdate()
    raw = get_str_setting(
        "savings.placement.closed_from", PLACEMENT_CLOSED_FROM_DEFAULT
    ).strip()
    try:
        closed_from = date.fromisoformat(raw)
    except ValueError:
        closed_from = date.fromisoformat(PLACEMENT_CLOSED_FROM_DEFAULT)
    return on < closed_from
