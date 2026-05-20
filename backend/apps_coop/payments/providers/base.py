"""Abstract interface every payment provider must implement.

Keep this file free of provider-specific concerns — only the contract.
The cooperative business code (`apps_coop.payments.services`) only ever
imports symbols defined here, never from a concrete provider module.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps_coop.payments.models import Payment


class ProviderError(Exception):
    """Wraps any non-recoverable error coming from a provider gateway."""

    def __init__(self, message: str, *, retryable: bool = False, raw: dict | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.raw = raw or {}


@dataclass
class InitPayinResult:
    """Returned by `init_payin()` — what we store on the local `Payment` row."""

    provider_reference: str
    payment_url: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class PayoutResult:
    """Returned by `init_payout()` — outbound transfer (e.g. loan disbursement)."""

    provider_reference: str
    raw: dict = field(default_factory=dict)


@dataclass
class WebhookEvent:
    """Normalised webhook payload — providers translate their native shapes
    into this common envelope so services.py never branches per provider.
    """

    payment_idempotency_key: str
    status: str  # "valide" | "en_attente" | "rejete"
    provider_reference: str
    raw: dict = field(default_factory=dict)


class PaymentProviderBase(ABC):
    """Interface every Mobile Money / card / wire provider must implement."""

    #: Stable short identifier, persisted on `Payment.provider_code`.
    code: str = ""

    @abstractmethod
    def init_payin(self, payment: "Payment", *, phone: str, network: str) -> InitPayinResult:
        """Push an inbound payment request to the user (USSD prompt for MoMo).

        Implementations MUST be idempotent: passing the same
        `payment.idempotency_key` twice must not create two transactions.
        """

    @abstractmethod
    def check_status(self, payment: "Payment") -> str:
        """Poll the gateway for the current status of an in-flight payment.

        Returns one of: ``"valide"`` | ``"en_attente"`` | ``"rejete"``.
        Used by the hourly reconciliation cron and by manual admin actions.
        """

    @abstractmethod
    def init_payout(self, payment: "Payment", *, recipient_phone: str, network: str) -> PayoutResult:
        """Wire money OUT to a beneficiary (used for loan disbursement)."""

    @abstractmethod
    def verify_webhook(self, body: bytes, signature_header: str) -> WebhookEvent:
        """Authenticate the webhook and translate its body into a `WebhookEvent`.

        MUST raise `ProviderError` if the signature is invalid — never return
        an event for an unauthenticated request.
        """
