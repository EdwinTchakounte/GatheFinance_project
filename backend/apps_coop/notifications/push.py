"""Envoi de notifications push — **bases** posées (FCM/APNs).

Objectif de ce module : fournir un point d'entrée unique ``send_push_to_user``
que le reste du code appelle *dès maintenant*, alors même que le fournisseur
(Firebase Cloud Messaging) n'est pas encore configuré. Tant qu'aucune clé
``FCM_*`` n'est présente, l'envoi est un **no-op loggé** (jamais d'erreur).

Quand les identifiants seront disponibles, il suffira d'implémenter
``_deliver`` (HTTP FCM v1) sans toucher aux appelants.

Best-effort : ce module n'échoue jamais — une notif push cassée ne doit pas
casser un flux métier.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def push_enabled() -> bool:
    """True si un fournisseur push est configuré (clé serveur présente)."""
    return bool(getattr(settings, "FCM_SERVER_KEY", "") or getattr(settings, "FCM_CREDENTIALS_JSON", ""))


def send_push_to_user(user, *, title: str, body: str, data: dict | None = None) -> int:
    """Tente d'envoyer un push à tous les appareils actifs de ``user``.

    Retourne le nombre d'envois tentés. No-op (0) si push non configuré ou
    aucun appareil. N'élève jamais d'exception.
    """
    try:
        # Court-circuit : tant qu'aucun fournisseur n'est configuré, on
        # n'interroge meme pas la table (evite une requete DB par notif).
        if not push_enabled():
            return 0

        from .models import DeviceToken

        tokens = list(
            DeviceToken.objects.filter(user=user, active=True).values_list(
                "token", "platform"
            )
        )
        if not tokens:
            return 0
        sent = 0
        for token, platform in tokens:
            if _deliver(token=token, platform=platform, title=title, body=body, data=data or {}):
                sent += 1
        return sent
    except Exception:  # noqa: BLE001 — le push ne doit jamais casser un flux
        logger.warning("send_push_to_user a échoué pour user #%s", getattr(user, "id", "?"), exc_info=True)
        return 0


def _deliver(*, token: str, platform: str, title: str, body: str, data: dict) -> bool:
    """Livraison réelle au fournisseur — à implémenter (FCM HTTP v1).

    Placeholder : tant que FCM n'est pas branché, on logge et on renvoie False.
    """
    logger.debug("push (stub) → %s/%s : %s", platform, token[:12], title)
    return False


def touch_last_seen(device_token) -> None:
    """Marque un jeton comme vu (best-effort)."""
    try:
        device_token.last_seen_at = timezone.now()
        device_token.save(update_fields=["last_seen_at", "updated_at"])
    except Exception:  # noqa: BLE001
        pass
