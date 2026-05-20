"""Payment provider registry — pluggable Mobile Money / card / wire gateways.

A `Payment` row carries `provider_code` (e.g. "tara"); the rest of the code
asks `get_provider(code)` and works against the abstract `PaymentProviderBase`
interface. Adding a new gateway = new file in this directory + one line below.
"""
from __future__ import annotations

from .base import (
    InitPayinResult,
    PaymentProviderBase,
    PayoutResult,
    ProviderError,
    WebhookEvent,
)
from .tara import TaraProvider


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


__all__ = [
    "get_provider",
    "PaymentProviderBase",
    "InitPayinResult",
    "PayoutResult",
    "WebhookEvent",
    "ProviderError",
    "TaraProvider",
]
