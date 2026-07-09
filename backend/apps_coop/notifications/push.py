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


_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
# Cache module-level du couple (Credentials, project_id) — google-auth ne
# rafraîchit le jeton OAuth (~1h) que lorsqu'il est expiré.
_FCM_CREDS = None


def _fcm_credentials():
    """(access_token, project_id) depuis le service account, ou None.

    Le JSON du compte de service vit dans ``settings.FCM_CREDENTIALS_JSON``
    (chaîne JSON en env). Imports google-auth **locaux** : le module reste
    importable même si la lib n'est pas installée (push dormant)."""
    global _FCM_CREDS
    raw = getattr(settings, "FCM_CREDENTIALS_JSON", "") or ""
    if not raw:
        return None
    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest

        if _FCM_CREDS is None:
            import json as _json

            from google.oauth2 import service_account

            info = _json.loads(raw) if isinstance(raw, str) else raw
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=[_FCM_SCOPE]
            )
            _FCM_CREDS = (creds, info.get("project_id", ""))
        creds, project_id = _FCM_CREDS
        if not creds.valid:
            creds.refresh(GoogleAuthRequest())
        return creds.token, project_id
    except Exception:  # noqa: BLE001 — credentials mal formées → push dormant.
        logger.warning("FCM: credentials invalides / google-auth absent.", exc_info=True)
        return None


def _deactivate_token(token: str) -> None:
    """Désactive un DeviceToken devenu invalide (app désinstallée, data effacée)."""
    try:
        from .models import DeviceToken

        DeviceToken.objects.filter(token=token, active=True).update(active=False)
    except Exception:  # noqa: BLE001
        pass


def _deliver(*, token: str, platform: str, title: str, body: str, data: dict) -> bool:
    """Livraison réelle via l'API FCM HTTP v1. Renvoie True si accepté (200).

    Best-effort : toute erreur → False (jamais d'exception). Un token invalide
    (``UNREGISTERED`` / 404) est désactivé pour ne plus l'interroger."""
    import requests

    creds = _fcm_credentials()
    if creds is None:
        return False
    access_token, project_id = creds
    if not project_id:
        return False

    message = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            # FCM data payload : valeurs en chaînes uniquement.
            "data": {str(k): str(v) for k, v in (data or {}).items()},
        }
    }
    try:
        resp = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            json=message,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        logger.warning("FCM: échec réseau vers %s/%s", platform, token[:12], exc_info=True)
        return False

    if resp.status_code == 200:
        return True
    text = (resp.text or "")[:300]
    if resp.status_code in (400, 403, 404) and (
        "UNREGISTERED" in text or "NOT_FOUND" in text or "INVALID_ARGUMENT" in text
    ):
        _deactivate_token(token)
    logger.warning("FCM send failed (%s) : %s", resp.status_code, text)
    return False


def touch_last_seen(device_token) -> None:
    """Marque un jeton comme vu (best-effort)."""
    try:
        device_token.last_seen_at = timezone.now()
        device_token.save(update_fields=["last_seen_at", "updated_at"])
    except Exception:  # noqa: BLE001
        pass
