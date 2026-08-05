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

import logging
from typing import TYPE_CHECKING

import requests
from django.conf import settings

from apps_coop.members.naming import full_name

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
        """Initie un paiement Tara — STK Push direct sur le téléphone.

        Contrat officiel Tara (doc 2026-06-25) :
          - ``productPrice`` est un INT (pas string)
          - ``phoneNumber`` requis au format ``2376xxxxxxx`` (sans +)
          - ``network`` optionnel (vide → Tara détecte via préfixe phone)
          - Réponse Cameroun (MTN/Orange) : ``{status, message, vendor}``
            → PAS de transactionId, PAS de paymentUrl, PAS de page hostée
          - Réponse Wave (SN/BF/CI) : ``{..., authUrl}`` → navigateur
          - Tara pousse un popup USSD/STK directement sur le téléphone du
            membre. Il valide avec son PIN MoMo. Le webhook arrive ensuite.
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
        # Payload aligne strictement sur la doc Tara (voir taramoney.com/developer).
        # Champs requis : apiKey, businessId, productId, productName,
        # productPrice (int), phoneNumber (sans +), webHookUrl.
        # Champs optionnels : network, productDescription, returnUrl,
        # productPictureUrl. On n'inclut un optionnel que s'il a une valeur.
        # Le membre paie le montant + les frais de transaction (%) : Tara
        # facture le TOTAL, les hooks métier ne créditent que `montant`.
        total_a_facturer = int(payment.montant) + int(payment.frais_transaction or 0)
        payload: dict = {
            "apiKey": self.api_key,
            "businessId": self.business_id,
            "productId": str(payment.idempotency_key),
            "productName": product_name,
            "productPrice": total_a_facturer,  # int XAF, montant + frais
            "phoneNumber": self._normalize_phone(phone),  # 2376xxxxxxx
            "webHookUrl": self._webhook_url(),
        }
        # network laisse vide -- Tara detecte le reseau a partir du prefixe
        # du phoneNumber (decision client 2026-06-25). Le caller passe
        # toujours un network MTN/ORANGE depuis le sheet versement (utilise
        # cote validation serializer) mais on ne le propage pas a Tara.
        payload["network"] = ""
        # productDescription + returnUrl optionnels : utiles pour la page
        # de checkout hostee (libelle marchand + URL de retour apres paiement).
        payload["productDescription"] = f"Paiement {product_name} — GATHE Finance"
        payload["returnUrl"] = self._return_url()
        data = self._post("/api/tara/mobilepay", payload)
        # Log explicite de la reponse Tara pour debug en prod : on veut
        # voir le status / message / vendor / authUrl quand le STK Push
        # ne semble pas arriver cote membre. Le payload sortant masque
        # apiKey/businessId mais montre productId/price/phoneNumber.
        logger.info(
            "[TARA] init_payin OK — phone=%s price=%s productId=%s → tara_response=%s",
            payload.get("phoneNumber"),
            payload.get("productPrice"),
            payload.get("productId"),
            data,
        )
        # Doc Tara 2026-06-25 — la réponse est :
        #   {status:"SUCCESS", message:"API_ORDER_SUCESSFULL", vendor:"ORANGE_CAMEROON"}
        # PAS de transactionId, PAS de paymentUrl. Le flow Tara pousse
        # directement un STK Push / popup USSD sur le téléphone du membre
        # via le `phoneNumber` envoyé — il valide avec son PIN MoMo.
        # Le webhook arrivera ensuite avec `collectionId = notre productId`.
        #
        # Pour Wave (Sénégal/Burkina/CI uniquement) la réponse contient un
        # `authUrl` à ouvrir en navigateur. Pour MTN/Orange Cameroun, NULL.
        return InitPayinResult(
            # Avant le webhook on n'a pas d'ID Tara — on garde notre
            # idempotency_key comme reference. Le `paymentId` final
            # arrivera dans le webhook.
            provider_reference=str(payment.idempotency_key),
            payment_url=data.get("authUrl"),  # Wave uniquement, sinon None
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
                full_name(payment.member.prenom, payment.member.nom)
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
        """Vérifie un webhook Tara — doc 2026-06-25.

        Tara NE SIGNE PAS le webhook (pas de HMAC, pas de header de
        signature, pas de secret partagé dans le body). La sécurité repose
        sur : (a) HTTPS du webHookUrl, (b) le fait que seule Tara connaît
        cette URL (on l'a fournie lors de l'init). Recommandation Tara :
        *"Ensure your webHookUrl is secured with HTTPS."*

        On vérifie quand même que le `businessId` du body correspond au
        nôtre — défense en profondeur contre un attaquant qui devinerait
        l'URL : il faudrait aussi qu'il connaisse notre TARA_BUSINESS_ID.

        Mapping body Tara → WebhookEvent :
          collectionId → payment_idempotency_key (= notre productId envoyé)
          paymentId    → provider_reference (= ID Tara, pour audit)
          status       → SUCCESS / FAILURE
        """
        try:
            payload = self._parse_json(body)
        except ValueError as exc:
            raise ProviderError(f"Malformed webhook body: {exc}", retryable=False) from exc

        # Défense en profondeur : refuse les webhooks qui ne ciblent pas
        # notre businessId Tara. Une URL secrète seule ne suffit pas.
        # Quand TARA_BUSINESS_ID est configuré, le `businessId` du body est
        # OBLIGATOIRE et doit correspondre — sinon un webhook forgé SANS
        # `businessId` contournait le contrôle (le `payload.get(...)` truthy
        # rendait la garde optionnelle). Combiné aux fallbacks de matching
        # (référence vide / téléphone), c'était un vecteur de confirmation
        # forgée sur un paiement en attente. On rend le champ requis.
        if self.business_id:
            incoming = payload.get("businessId")
            if not incoming or str(incoming) != str(self.business_id):
                raise ProviderError(
                    f"Webhook businessId invalide ou absent: got {incoming!r}",
                    retryable=False,
                )

        return WebhookEvent(
            # `productId` est notre UUID idempotency_key envoye a l'init . c'est
            # la cle de matching cote GATHE. `collectionId` est l'ID INTERNE
            # Tara (numerique) qu'on garde en provider_reference, jamais comme
            # cle de matching. Confirme sur prod 2026-06-26 : Tara renvoie
            # bien notre productId UUID dans le webhook, le fallback
            # collectionId reste en cas d'anciens webhooks Tara qui ne
            # propageaient pas productId.
            payment_idempotency_key=str(
                payload.get("productId") or payload.get("collectionId") or "",
            ),
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
