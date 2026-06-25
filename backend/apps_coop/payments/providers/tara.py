"""Tara Money provider implementation.

Docs reference: https://taramoney.com/developer (May 2026).

Mapping decisions:
  - We use our `Payment.idempotency_key` (UUID) as Tara's `productId`. This
    gives Tara a stable handle to dedupe retries and gives us a way to look
    up the local Payment from a webhook payload without exposing our DB ids.
  - We send `webHookUrl` per request (Tara supports overriding per call) so
    different environments (sandbox / staging / prod) get their own callback.
  - Tara's networks: "MTN" | "ORANGE" | "WAVE" | ... — we forward the value
    the caller passes; validation lives at the serializer layer.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import TYPE_CHECKING

import requests
from django.conf import settings

from .base import (
    InitPayinResult,
    PaymentProviderBase,
    PayoutResult,
    ProviderError,
    WebhookEvent,
)

if TYPE_CHECKING:
    from apps_coop.payments.models import Payment


logger = logging.getLogger(__name__)


class TaraProvider(PaymentProviderBase):
    code = "tara"
    # Les endpoints Tara sont servis sur dklo.co (confirmé via doc développeur
    # taramoney.com → developers). PAS sur taramoney.com.
    BASE_URL = "https://www.dklo.co"
    TIMEOUT_SECONDS = 15

    # -- Configuration -------------------------------------------------------

    def __init__(self) -> None:
        self.api_key = getattr(settings, "TARA_API_KEY", "") or ""
        self.business_id = getattr(settings, "TARA_BUSINESS_ID", "") or ""
        self.webhook_secret = getattr(settings, "TARA_WEBHOOK_SECRET", "") or ""

    def _require_credentials(self) -> None:
        if not (self.api_key and self.business_id):
            raise ProviderError(
                "Tara credentials are not configured (TARA_API_KEY / TARA_BUSINESS_ID).",
                retryable=False,
            )

    @property
    def _mock_mode(self) -> bool:
        """Dev convenience: when no Tara credentials are configured, skip the
        outbound HTTP call entirely and return a fake reference. Pairs with
        the dev-only ``POST /api/v1/payments/dev/<id>/confirm/`` endpoint that
        simulates the webhook locally.
        """
        return not (self.api_key and self.business_id)

    # -- Payin (inbound payment from member) --------------------------------

    def init_payin(self, payment: "Payment", *, phone: str, network: str) -> InitPayinResult:
        """Crée un ordre de paiement Tara — page de paiement hostée.

        Contrat officiel Tara (validé 2026-06-25 par tests live) :
          - ``productPrice`` est un INT (pas string)
          - PAS de ``phoneNumber`` / ``network`` au top level — Tara héberge
            une page où l'utilisateur choisit son opérateur lui-même
          - Réponse SUCCESS : ``{status, message, transactionId, ...}``
          - L'URL de checkout est construite : ``BASE_URL/c/<transactionId>``

        ``phone`` et ``network`` reçus en paramètres sont conservés en raw
        pour audit, et passés en query string sur ``returnUrl`` pour
        pré-remplir le formulaire Tara côté membre.
        """
        if self._mock_mode:
            logger.warning(
                "TaraProvider in MOCK mode (no API key) — skipping HTTP and returning a fake reference."
            )
            return InitPayinResult(
                provider_reference=f"MOCK-{payment.idempotency_key}",
                payment_url=None,
                raw={"mock": True, "reason": "TARA_API_KEY not configured"},
            )
        product_name = (
            payment.get_type_display() if hasattr(payment, "get_type_display") else payment.type
        )
        payload = {
            "apiKey": self.api_key,
            "businessId": self.business_id,
            "productId": str(payment.idempotency_key),
            "productName": product_name,
            "productPrice": int(payment.montant),  # Tara veut un int en XAF
            "productDescription": f"Paiement {product_name} — Gathé Finance",
            "returnUrl": self._return_url(),
            "webHookUrl": self._webhook_url(),
        }
        data = self._post("/api/tara/mobilepay", payload)
        # SUCCESS → ``{status:"SUCCESS", message:"API_ORDER_SUCESSFULL",
        #             transactionId:"1776478264", price:0, transactionList:[]}``
        transaction_id = (
            data.get("transactionId")
            or data.get("paymentId")
            or str(payment.idempotency_key)
        )
        # URL de checkout Tara : on construit depuis transactionId. Si la
        # réponse contient explicitement un ``paymentUrl``, on le préfère.
        payment_url = data.get("paymentUrl") or f"{self.BASE_URL}/c/{transaction_id}"
        return InitPayinResult(
            provider_reference=str(transaction_id),
            payment_url=payment_url,
            raw={**data, "_hint_phone": phone, "_hint_network": network},
        )

    # -- Status poll (used by the hourly reconciliation cron) ----------------

    def check_status(self, payment: "Payment") -> str:
        if self._mock_mode:
            # Mock mode never auto-confirms — confirmation happens via the dev endpoint.
            return "en_attente"
        payload = {
            "apiKey": self.api_key,
            "businessId": self.business_id,
            "productId": str(payment.idempotency_key),
        }
        data = self._post("/api/tara/transactions/status", payload)
        raw_status = (data.get("status") or "").upper()
        return _STATUS_MAP.get(raw_status, "en_attente")

    # -- Payout (outbound — e.g. loan disbursement) -------------------------

    def init_payout(self, payment: "Payment", *, recipient_phone: str, network: str) -> PayoutResult:
        if self._mock_mode:
            logger.warning("TaraProvider payout in MOCK mode — returning a fake reference.")
            return PayoutResult(
                provider_reference=f"MOCK-PAYOUT-{payment.idempotency_key}",
                raw={"mock": True},
            )
        payload = {
            "apiKey": self.api_key,
            "businessId": self.business_id,
            "receiverName": (
                f"{payment.member.prenom} {payment.member.nom}"
                if getattr(payment, "member_id", None)
                else ""
            ),
            "paymentMethod": "MOBILE_MONEY",
            "receiverPhoneNumber": self._normalize_phone(recipient_phone),
            "receiverId": self._normalize_phone(recipient_phone),
            "amount": str(int(payment.montant)),
            # `network` not used by `/payout/create` per docs, but we keep it
            # in raw for traceability.
            "network": network.upper(),
        }
        # NB: la doc Tara orthographie littéralement « paypout » (probable
        # typo côté Tara, mais c'est le path réel attendu par leur API).
        data = self._post("/api/tara/paypout/create", payload)
        return PayoutResult(
            provider_reference=str(data.get("payoutId") or ""),
            raw=data,
        )

    # -- Webhook authentication + normalisation ------------------------------

    def verify_webhook(self, body: bytes, signature_header: str) -> WebhookEvent:
        if not self.webhook_secret:
            raise ProviderError(
                "TARA_WEBHOOK_SECRET is not configured — refusing to process the webhook.",
                retryable=False,
            )
        expected = hmac.new(
            self.webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not (signature_header and hmac.compare_digest(expected, signature_header)):
            raise ProviderError("Invalid HMAC signature on Tara webhook", retryable=False)

        try:
            payload = self._parse_json(body)
        except ValueError as exc:
            raise ProviderError(f"Malformed webhook body: {exc}", retryable=False) from exc

        return WebhookEvent(
            payment_idempotency_key=str(payload.get("productId") or ""),
            status=_STATUS_MAP.get((payload.get("status") or "").upper(), "en_attente"),
            provider_reference=str(payload.get("paymentId") or ""),
            raw=payload,
        )

    # -- Internals ----------------------------------------------------------

    def _webhook_url(self) -> str:
        base = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
        return f"{base}/api/v1/payments/webhook/tara/"

    def _return_url(self) -> str:
        """URL de retour après checkout Tara — page vitrine qui affiche un
        statut au membre. Le webhook arrive en parallèle côté backend.
        """
        base = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
        # On pointe vers la racine — le navigateur revient en mode "Paiement
        # terminé" simple. À termes une page /payment-return/<id>/ pourrait
        # surfacer plus de détails au membre.
        return f"{base}/"

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = requests.post(
                f"{self.BASE_URL}{path}",
                json=payload,
                timeout=self.TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            raise ProviderError(f"Tara timeout on {path}", retryable=True) from exc
        except requests.RequestException as exc:
            raise ProviderError(f"Tara network error on {path}: {exc}", retryable=True) from exc

        if response.status_code >= 500:
            raise ProviderError(
                f"Tara 5xx on {path}: {response.status_code}",
                retryable=True,
                raw={"status_code": response.status_code, "body": response.text[:500]},
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                f"Tara returned non-JSON on {path}: {response.text[:200]}",
                retryable=False,
            ) from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"Tara error on {path}: {data.get('message') or response.status_code}",
                retryable=False,
                raw=data,
            )
        # Tara surfaces business errors with status 200 sometimes.
        if (data.get("status") or "").upper() in {"ERROR", "FAILED"}:
            raise ProviderError(
                f"Tara business error: {data.get('message') or 'unknown'}",
                retryable=False,
                raw=data,
            )
        return data

    @staticmethod
    def _parse_json(body: bytes) -> dict:
        import json

        return json.loads(body.decode("utf-8") or "{}")

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        """Tara expects Cameroon numbers as ``2376xxxxxxx`` (no plus, no spaces)."""
        digits = "".join(c for c in (raw or "") if c.isdigit())
        if not digits:
            raise ProviderError("Empty phone number", retryable=False)
        if digits.startswith("237"):
            return digits
        # Tolerate leading 0 (national format) → strip it then prefix 237
        return f"237{digits.lstrip('0')}"


# Mapping table for Tara → internal Payment.statut.
# Kept module-level so it's easy to extend without touching the class body.
_STATUS_MAP: dict[str, str] = {
    "SUCCESS": "valide",
    "VALIDATED": "valide",
    "COMPLETED": "valide",
    "PAID": "valide",
    "PENDING": "en_attente",
    "INITIATED": "en_attente",
    "FAILED": "rejete",
    "REJECTED": "rejete",
    "CANCELLED": "rejete",
    "ERROR": "rejete",
}
