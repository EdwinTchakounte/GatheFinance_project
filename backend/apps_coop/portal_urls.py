"""Single source of truth for building portal-facing URLs.

Every transactional link sent by e-mail (welcome / password setup / loan
approved / payment receipt / lender consent / etc.) MUST point to the member
portal (`portail.gathe-finance.horus-lab.com`), never to the marketing site
(`gathe-finance.horus-lab.com`) — sending a member to the wrong sub-domain
guarantees a 404.

Use ``portal_url(path)`` everywhere. Don't read ``FRONTEND_PUBLIC_URL`` /
``FRONTEND_BASE_URL`` directly: ``FRONTEND_BASE_URL`` is the marketing
site URL and using it for member links is the bug we keep re-introducing.
"""
from __future__ import annotations

import logging
import os
import re

from django.conf import settings

logger = logging.getLogger(__name__)


_VALID_URL_RE = re.compile(r"^https?://[^/\s]+")


def portal_base() -> str:
    """Return the public base URL of the member portal (no trailing slash).

    Resolution order (defensive, prod-first):

    1. ``settings.FRONTEND_PUBLIC_URL`` — explicit, expected in prod
       (set via ``FRONTEND_PUBLIC_URL`` env var on the backend container).
    2. Derived from ``PORTAL_DOMAIN`` env var — fallback if the settings
       wiring was forgotten on the VPS. Reads the env var directly so a
       misconfigured ``settings.py`` cannot mask the value.
    3. ``http://localhost:3200`` — dev/test only. In prod
       (``DEBUG=False``) we log an error so the misconfiguration is loud
       in Sentry / log aggregator.
    """
    url = (getattr(settings, "FRONTEND_PUBLIC_URL", "") or "").strip().rstrip("/")
    if url and _VALID_URL_RE.match(url):
        return url

    domain = os.environ.get("PORTAL_DOMAIN", "").strip().rstrip("/")
    if domain:
        derived = f"https://{domain}"
        logger.warning(
            "portal_urls: FRONTEND_PUBLIC_URL unset or invalid (got %r) — "
            "falling back to https://PORTAL_DOMAIN (%s).",
            url, derived,
        )
        return derived

    fallback = "http://localhost:3200"
    if not getattr(settings, "DEBUG", False):
        logger.error(
            "portal_urls: neither FRONTEND_PUBLIC_URL nor PORTAL_DOMAIN are "
            "configured in prod — transactional links will 404. Falling back "
            "to %s. Set FRONTEND_PUBLIC_URL on the backend container.",
            fallback,
        )
    return fallback


def portal_url(path: str = "") -> str:
    """Return an absolute portal URL for ``path`` (leading slash optional).

    >>> portal_url()              # base
    'https://portail.gathe-finance.horus-lab.com'
    >>> portal_url("connexion")   # auto leading slash
    'https://portail.gathe-finance.horus-lab.com/connexion'
    >>> portal_url("/credit")     # leading slash kept
    'https://portail.gathe-finance.horus-lab.com/credit'
    """
    base = portal_base()
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"
