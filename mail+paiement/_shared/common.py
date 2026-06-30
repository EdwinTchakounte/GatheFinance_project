"""Shared mixins, helpers and money config for all cooperative business apps.

Kept dependency-free so any app under `apps_coop/` can import without cycles.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import models


MONEY_MAX_DIGITS = 14
MONEY_DECIMAL_PLACES = 2
ZERO = Decimal("0.00")


def money_field(**kwargs) -> models.DecimalField:
    """Standard money column. Always pass a sensible `default=` for non-null cases."""
    return models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        **kwargs,
    )


class TimestampedModel(models.Model):
    """Adds `created_at` and `updated_at` columns to any model that inherits it."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def parse_pagination(
    request,
    default_limit: int = 25,
    max_limit: int = 200,
) -> tuple[int, int]:
    """Lit ``?limit=`` et ``?offset=`` depuis la querystring, avec cap defensif.

    Renvoie ``(offset, limit)`` valides (clamp + fallback sur defaut si
    valeur invalide). Utilise par tous les endpoints admin listes pour
    une UX de pagination coherente cote dashboard Next.js.
    """
    qp = request.query_params
    try:
        limit = int(qp.get("limit") or default_limit)
    except (TypeError, ValueError):
        limit = default_limit
    limit = max(1, min(limit, max_limit))

    try:
        offset = int(qp.get("offset") or 0)
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    return offset, limit
