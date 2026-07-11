"""Helpers to write AuditLog rows from anywhere in the code.

Use `record(...)` for explicit business events (e.g. loan.approve, member.suspend).
The HTTP middleware writes coarser entries automatically — service layer code
should still call `record()` for finer-grained, semantic events that show
*why* something happened, not just that a request hit an endpoint.
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from .models import AuditLog


def record(
    *,
    action: str,
    entite_type: str = "",
    entite_id: int | None = None,
    user: Any = None,
    details: dict | None = None,
    ip: str | None = None,
    user_agent: str = "",
) -> AuditLog:
    """Write a single AuditLog row. Never raises — audit must never break flows."""
    User = get_user_model()
    if user is not None and not isinstance(user, User) and not getattr(user, "is_authenticated", False):
        user = None
    try:
        return AuditLog.objects.create(
            user=user if (user and getattr(user, "is_authenticated", False)) else None,
            action=action,
            entite_type=entite_type,
            entite_id=entite_id,
            details_json=details or {},
            ip=ip,
            user_agent=user_agent[:255],
        )
    except Exception:  # pragma: no cover — audit must be best-effort
        import logging

        logging.getLogger(__name__).exception("Failed to write AuditLog row")
        return None  # type: ignore[return-value]


def client_ip(request) -> str | None:
    """Resolve the client IP, trusting X-Forwarded-For only if the reverse
    proxy sets it (we rely on settings.SECURE_PROXY_SSL_HEADER in prod).
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# ---------------------------------------------------------------------------
# AppSetting helpers — admin-tunable scalars without redeploy (EXT-1).
# ---------------------------------------------------------------------------
#
# A `record()` is always written via audit middleware when an admin edits an
# AppSetting from the Django admin; the helpers below only READ. They NEVER
# raise — DB unavailable / table not migrated / value missing all fall back
# to the regulatory default supplied by the caller.

# Cache des AppSetting : lues très fréquemment (chemin chaud) mais quasi-
# immuables → mémoïsées (TTL settings.CACHES) + invalidées à l'écriture via le
# signal post_save/post_delete sur AppSetting (voir apps_coop/audit/models.py).
_SETTING_MISS = "\x00__miss__\x00"  # sentinelle "clé absente" (distinct de None)


def setting_cache_key(key: str) -> str:
    return f"appsetting:{key}"


def _read_setting_raw(key: str) -> str | None:
    """Valeur brute (str) de l'AppSetting ``key``, ou ``None`` si absente.

    Mémoïsée (cache local) + invalidée à l'écriture. Ne lève JAMAIS : cache/DB
    indisponible → ``None`` (le caller applique alors son défaut réglementaire).
    """
    try:
        from django.core.cache import cache

        ck = setting_cache_key(key)
        cached = cache.get(ck)
        if cached is not None:
            return None if cached == _SETTING_MISS else cached

        from .models import AppSetting

        raw = (
            AppSetting.objects.filter(cle=key)
            .values_list("valeur", flat=True)
            .first()
        )
        val = None if raw is None or raw == "" else str(raw)
        cache.set(ck, _SETTING_MISS if val is None else val)
        return val
    except Exception:  # noqa: BLE001 — table non migrée / DB ou cache indispo
        return None


def get_int_setting(key: str, default: int) -> int:
    """Read an integer AppSetting by ``key``; fall back to ``default``.

    Used for tunable scalars (contentieux threshold, due-soon lead, renewal
    extra months, cut-off hour…). The caller's ``default`` mirrors the
    regulatory value so the system stays correct even before the seed runs.
    """
    raw = _read_setting_raw(key)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        import logging

        logging.getLogger(__name__).warning(
            "get_int_setting(%s) — valeur %r non entière, défaut %s",
            key,
            raw,
            default,
        )
        return default


def get_str_setting(key: str, default: str) -> str:
    """Read a string AppSetting by ``key``; fall back to ``default``."""
    raw = _read_setting_raw(key)
    return default if raw is None else raw
