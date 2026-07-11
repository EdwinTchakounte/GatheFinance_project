"""Accès centralisé aux taux métier modifiables (BR2).

Les taux vivent en base (`RateParam`) pour qu'un admin puisse les ajuster sans
déploiement. Chaque taux a un **défaut réglementaire** (``loans/terms.py`` /
``savings/cutoff.py``) qui sert de fallback sûr quand la ligne DB est absente
ou que la table n'est pas encore migrée (tests, install fraîche, cron avant
seed). Aucun appel ne doit jamais planter faute de configuration.

Usage côté services :

    from apps_coop.payments.rates import get_rate
    from apps_coop.payments.models import RateParam

    taux = get_rate(RateParam.Code.LOAN_INTEREST)
"""
from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def _defaults() -> dict[str, Decimal]:
    """Défauts réglementaires, source de vérité = terms.py / cutoff.py.

    Import paresseux : ces modules ne dépendent pas de ``payments`` (pas de
    cycle), mais on les charge à l'appel pour rester découplé.
    """
    from apps_coop.loans.terms import LOAN_INTEREST_RATE, RenewalRate
    from apps_coop.savings.cutoff import MONTHLY_INTEREST_RATE

    return {
        "LOAN_INTEREST": LOAN_INTEREST_RATE,
        "SAVINGS_INTEREST_MONTHLY": MONTHLY_INTEREST_RATE,
        "RENEWAL_CASH": RenewalRate.INTERETS_AU_COMPTANT,
        "RENEWAL_DEFERRED": RenewalRate.INTERETS_REPORTES,
        "LATE_PENALTY": RenewalRate.PENALITE_NON_VERSEMENT,
        # Frais de transaction sur versement : 0 par défaut (aucun frais tant
        # que l'admin n'a pas fixé un pourcentage).
        "TRANSACTION_FEE": Decimal("0"),
    }


def default_rate(code: str) -> Decimal:
    """Défaut réglementaire pour ``code``. Lève ``KeyError`` si inconnu."""
    defaults = _defaults()
    if code not in defaults:
        raise KeyError(f"Code de taux inconnu : {code!r}")
    return Decimal(defaults[code])


_RATE_MISS = "\x00__miss__\x00"  # sentinelle "pas de ligne DB" (≠ None)


def rate_cache_key(code: str) -> str:
    return f"rate:{code}"


def get_rate(code: str) -> Decimal:
    """Taux courant pour ``code`` : valeur DB si présente+active, sinon défaut.

    Mémoïsé (cache local, TTL court) + invalidé à l'écriture d'un ``RateParam``
    (signal, voir payments/models.py). Ne lève jamais : DB/cache indisponible →
    défaut réglementaire (les calculs restent corrects même sans seed).
    """
    default = default_rate(code)  # valide aussi le code (KeyError si inconnu)
    try:
        from django.core.cache import cache

        ck = rate_cache_key(code)
        cached = cache.get(ck)
        if cached is not None:
            return default if cached == _RATE_MISS else Decimal(cached)

        from .models import RateParam

        valeur = (
            RateParam.objects.filter(code=code, actif=True)
            .values_list("valeur", flat=True)
            .first()
        )
        cache.set(ck, _RATE_MISS if valeur is None else str(valeur))
        return default if valeur is None else Decimal(valeur)
    except Exception:  # table non migrée / DB ou cache indisponible
        logger.warning("get_rate(%s) — DB indisponible, défaut réglementaire", code)
        return default
