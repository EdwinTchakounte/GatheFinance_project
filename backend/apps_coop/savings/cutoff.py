"""Règles d'épargne (Règlement Intérieur, Article 4).

Concentre :
  - le **cut-off journalier** ``DAILY_CUTOFF_HOUR`` + helper ``compute_value_date`` ;
  - le **lieu d'agence** (canal de secours, l'app étant le canal principal) ;
  - le **taux d'intérêt mensuel** crédité par le cron du 1er du mois.

Le ``next business day`` est calculé en sautant samedi et dimanche. Les jours
fériés camerounais ne sont pas modélisés ici (pas indispensable pour le MVP,
ajoutables ultérieurement si besoin).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal


#: Heure UTC+1 (Douala) à partir de laquelle un dépôt est posté à J+1 ouvré.
DAILY_CUTOFF_HOUR = 17

#: Libellé du lieu d'agence (canal de secours).
COLLECTION_LOCATION = "GATHE FINANCE — Akwa Douala Bercy"

#: Taux d'intérêt crédité chaque mois sur le solde d'épargne (Article 4).
#: ``1 % par mois sur les sommes collectées``.
MONTHLY_INTEREST_RATE = Decimal("0.01")

#: Solde minimum sous lequel on ne crédite pas d'intérêt (évite des
#: SavingsTransaction à 0 ou 1 FCFA qui polluent l'historique).
MIN_BALANCE_FOR_INTEREST = Decimal("100")


def _next_business_day(d: date) -> date:
    """Retourne le prochain jour ouvré strict (lun–ven) après ``d``."""
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:  # 5 = samedi, 6 = dimanche
        nxt += timedelta(days=1)
    return nxt


def compute_value_date(now: datetime) -> date:
    """Date de valeur pour un versement effectué à ``now``.

    - Si ``now`` ≤ 17h00 ET ``now`` est un jour ouvré → date du jour.
    - Sinon → prochain jour ouvré.
    """
    today = now.date()
    is_business_day = today.weekday() < 5
    before_cutoff = now.time() < time(DAILY_CUTOFF_HOUR, 0)

    if is_business_day and before_cutoff:
        return today
    return _next_business_day(today)
