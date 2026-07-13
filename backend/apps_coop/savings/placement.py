"""Fenêtre du placement épargne classique (fermeture datée).

Le placement (sous-canal bloqué qui finance les crédits) FERME à une date-
limite : au-delà, tout nouveau versement d'épargne classique va en LIBRE et
l'ajout d'une tranche de placement est refusé. Les placements DÉJÀ existants ne
sont pas touchés — seuls les NOUVEAUX sont bloqués.

Décision client (2026-07-11) : fermeture au **1er août 2026**.

Trois verrous, tous tunables sans déploiement (AppSetting) :
  - ``epargne.placement.enabled``            : on/off global (défaut "true") ;
  - ``savings.placement.closed_from``        : date ISO de fermeture globale
    (défaut "2026-08-01") ;
  - ``epargne.placement.eligibility_months`` : fenêtre PAR MEMBRE — le placement
    n'est ouvert que pendant les N premiers mois d'ancienneté depuis l'adhésion
    (défaut 6). Passé ce délai, seule l'épargne LIBRE reste possible. Mettre 0
    (ou négatif) désactive la fenêtre par membre (seul le verrou global joue).
"""
from __future__ import annotations

from datetime import date

PLACEMENT_CLOSED_FROM_DEFAULT = "2026-08-01"

#: Nombre de mois d'éligibilité au placement depuis l'adhésion (défaut métier).
PLACEMENT_ELIGIBILITY_MONTHS_DEFAULT = 6


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


def placement_eligibility_months() -> int:
    """Fenêtre d'éligibilité au placement, en mois depuis l'adhésion (AppSetting)."""
    from apps_coop.audit.services import get_int_setting

    return get_int_setting(
        "epargne.placement.eligibility_months",
        PLACEMENT_ELIGIBILITY_MONTHS_DEFAULT,
    )


def placement_open_for_member(member, on: date | None = None) -> bool:
    """True si CE membre peut encore verser en placement.

    Combine le verrou global (``placement_open``) ET la fenêtre par membre :
    le placement n'est ouvert que pendant les N premiers mois d'ancienneté
    (``epargne.placement.eligibility_months``, défaut 6) depuis l'adhésion.
    Au-delà, seule l'épargne LIBRE reste possible. Ne lève jamais.
    """
    if not placement_open(on):
        return False
    if member is None:
        return False
    months = placement_eligibility_months()
    if months <= 0:
        # Fenêtre par membre désactivée → on ne garde que le verrou global.
        return True
    try:
        anciennete = int(member.seniority_months)
    except Exception:  # noqa: BLE001 — membre sans date_adhesion / propriété absente
        return False
    return anciennete < months
