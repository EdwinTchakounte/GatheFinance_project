"""Middleware de sécurité — blacklist des IP au trafic anormal.

Deux couches :
  1. **Blocage à l'entrée** : toute requête d'une IP au ban actif (table
     ``BlockedIP``) reçoit un 403 immédiat, avant tout traitement métier. La
     liste des IP bannies est mise en cache quelques secondes pour éviter un
     accès base à chaque requête.
  2. **Détection de flood** : compteur en fenêtre glissante PAR PROCESS
     (best-effort, sans Redis). Quand une IP dépasse le seuil, on écrit un
     ``BlockedIP`` temporaire → le ban devient GLOBAL (tous les workers le
     voient dès la requête suivante, via la base + le cache court).

Réglages (``settings``, valeurs par défaut entre parenthèses) :
  ``SECURITY_IP_BLOCK_ENABLED``        (True)  — active/désactive tout.
  ``SECURITY_IP_FLOOD_MAX_REQUESTS``   (240)   — requêtes autorisées…
  ``SECURITY_IP_FLOOD_WINDOW_SEC``     (60)    — …par fenêtre glissante (s).
  ``SECURITY_IP_BAN_MINUTES``          (30)    — durée d'un ban auto (0 = perm.).
  ``SECURITY_IP_WHITELIST``            ([])    — IP jamais bannies.
  ``SECURITY_IP_BLOCKLIST_CACHE_SEC``  (10)    — TTL du cache de la blacklist.

Le seuil par défaut (240 req/60 s/IP) est très au-dessus d'un usage humain
normal (une page charge plusieurs endpoints) mais écrête les bots/scrapers.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

from .services import client_ip


logger = logging.getLogger(__name__)

_BLOCKLIST_CACHE_KEY = "security:blocked_ips"

# Fenêtre glissante PAR PROCESS : ip -> deque[timestamps monotoniques].
_windows: "defaultdict[str, deque]" = defaultdict(deque)
# Compteur d'appels pour déclencher un balayage périodique des fenêtres vides.
_calls_since_sweep = 0
_SWEEP_EVERY = 500


def _cfg(name: str, default):
    return getattr(settings, name, default)


def _active_blocked_ips() -> set[str]:
    """Ensemble des IP au ban actif, caché quelques secondes (chemin chaud)."""
    cached = cache.get(_BLOCKLIST_CACHE_KEY)
    if cached is not None:
        return cached

    from django.db.models import Q

    from .models import BlockedIP

    now = timezone.now()
    ips = set(
        BlockedIP.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).values_list("ip", flat=True)
    )
    cache.set(_BLOCKLIST_CACHE_KEY, ips, _cfg("SECURITY_IP_BLOCKLIST_CACHE_SEC", 10))
    return ips


def invalidate_blocklist_cache() -> None:
    cache.delete(_BLOCKLIST_CACHE_KEY)


def _sweep_windows(now: float, window: int) -> None:
    """Purge les fenêtres vides/obsolètes pour borner la mémoire."""
    cutoff = now - window
    for ip in list(_windows.keys()):
        dq = _windows[ip]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if not dq:
            del _windows[ip]


def _register_and_check_flood(ip: str) -> bool:
    """Enregistre le hit ; retourne True si l'IP vient de dépasser le seuil."""
    global _calls_since_sweep

    window = _cfg("SECURITY_IP_FLOOD_WINDOW_SEC", 60)
    limit = _cfg("SECURITY_IP_FLOOD_MAX_REQUESTS", 240)
    now = time.monotonic()

    dq = _windows[ip]
    dq.append(now)
    cutoff = now - window
    while dq and dq[0] < cutoff:
        dq.popleft()
    # Garde-fou mémoire : on ne garde jamais plus que le seuil + marge.
    while len(dq) > limit + 50:
        dq.popleft()

    _calls_since_sweep += 1
    if _calls_since_sweep >= _SWEEP_EVERY:
        _calls_since_sweep = 0
        _sweep_windows(now, window)

    return len(dq) > limit


def _ban_ip(ip: str, reason: str) -> None:
    """Pose (ou ré-arme) un ban AUTO en base. Ne touche jamais un ban manuel."""
    from .models import BlockedIP

    minutes = _cfg("SECURITY_IP_BAN_MINUTES", 30)
    expires = timezone.now() + timedelta(minutes=minutes) if minutes else None

    obj, created = BlockedIP.objects.get_or_create(
        ip=ip,
        defaults={"reason": reason, "auto": True, "expires_at": expires},
    )
    if not created and obj.auto and not obj.is_active():
        # Ban auto expiré et l'IP re-floode → on ré-arme (jamais un ban manuel).
        obj.reason = reason
        obj.expires_at = expires
        obj.save(update_fields=["reason", "expires_at", "updated_at"])
    invalidate_blocklist_cache()
    logger.warning("IP bannie automatiquement (trafic anormal) : %s", ip)


class BlockedIPMiddleware:
    """Rejette les IP bannies + auto-bannit les IP au trafic anormal."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _cfg("SECURITY_IP_BLOCK_ENABLED", True):
            ip = client_ip(request)
            if ip and ip not in set(_cfg("SECURITY_IP_WHITELIST", [])):
                if ip in _active_blocked_ips():
                    return self._blocked()
                if _register_and_check_flood(ip):
                    try:
                        _ban_ip(ip, "Trafic anormal (flood auto-détecté).")
                    except Exception:  # noqa: BLE001 — best-effort, ne casse pas
                        logger.exception("Échec de la pose du ban auto (%s)", ip)
                    return self._blocked()
        return self.get_response(request)

    @staticmethod
    def _blocked() -> JsonResponse:
        return JsonResponse(
            {"detail": "Accès temporairement bloqué (trafic anormal détecté)."},
            status=403,
        )
