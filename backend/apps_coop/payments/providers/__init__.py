"""Payment provider registry — pluggable Mobile Money / card / wire gateways.

A `Payment` row carries `provider_code` (e.g. "tara"); the rest of the code
asks `get_provider(code)` and works against the abstract `PaymentProviderBase`
interface. Adding a new gateway = new file in this directory + one line below.
"""
from __future__ import annotations

import logging

from .base import (
    InitPayinResult,
    PaymentProviderBase,
    PayoutResult,
    ProviderError,
    WebhookEvent,
)
from .tara import TaraProvider


logger = logging.getLogger(__name__)

#: Ultime filet : ce provider est toujours enregistré, on y retombe si le
#: réglage ``DEFAULT_PAYMENT_PROVIDER`` pointe vers un code inconnu (typo env).
_FALLBACK_PROVIDER_CODE = TaraProvider.code

_PROVIDERS: dict[str, type[PaymentProviderBase]] = {
    TaraProvider.code: TaraProvider,
}


def get_provider(code: str) -> PaymentProviderBase:
    """Return a fresh provider instance for the given code.

    Raises `ValueError` if the code is not registered — this is on purpose:
    we want a hard fail rather than a silent no-op.
    """
    try:
        provider_cls = _PROVIDERS[code]
    except KeyError as exc:
        raise ValueError(f"Unknown payment provider: {code!r}") from exc
    return provider_cls()


def default_provider_code() -> str:
    """Code du prestataire par défaut pour un NOUVEAU paiement sortant.

    Lit ``settings.DEFAULT_PAYMENT_PROVIDER``. Si ce réglage pointe vers un code
    non enregistré (typo dans l'env), on **ne bloque pas** les paiements : on
    journalise et on retombe sur le provider de secours (toujours enregistré).
    Un système de paiement ne doit pas tomber entier sur une faute de frappe.
    """
    from django.conf import settings

    code = getattr(settings, "DEFAULT_PAYMENT_PROVIDER", "") or _FALLBACK_PROVIDER_CODE
    if code not in _PROVIDERS:
        logger.warning(
            "DEFAULT_PAYMENT_PROVIDER=%r n'est pas un prestataire enregistré — "
            "repli sur %r. Vérifie le réglage / l'enregistrement du provider.",
            code, _FALLBACK_PROVIDER_CODE,
        )
        return _FALLBACK_PROVIDER_CODE
    return code


__all__ = [
    "get_provider",
    "default_provider_code",
    "PaymentProviderBase",
    "InitPayinResult",
    "PayoutResult",
    "WebhookEvent",
    "ProviderError",
    "TaraProvider",
]
