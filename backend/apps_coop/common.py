"""Shared mixins, helpers and money config for all cooperative business apps.

Kept dependency-free so any app under `apps_coop/` can import without cycles.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
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


class AntidatableLedgerMixin(models.Model):
    """Champs communs aux écritures ledger susceptibles d'être SAISIES ANTIDATÉES
    (reprise d'historique papier) puis INVALIDÉES (contre-passation).

    - ``is_antidated`` : repère FIABLE d'une écriture créée par le service de
      saisie antidatée. ``payment=None`` ne suffit pas (un retrait normal l'est
      aussi) : ce flag est la source de vérité de l'onglet « Saisies antidatées »
      et le seul filtre sûr pour ne lister QUE les antidatées.
    - ``reversed_at`` / ``reversed_by`` / ``reversal_note`` : trace d'une
      invalidation. L'écriture d'origine reste en base (ledger append-only) mais
      est marquée invalidée (barrée en historique) ; son effet sur le solde est
      contre-passé par une écriture inverse. ``reversed_at`` non nul ⇒ déjà
      invalidée (idempotence, sans dépendre de l'audit).
    """

    is_antidated = models.BooleanField(default=False, db_index=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reversal_note = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        abstract = True

    @property
    def is_reversed(self) -> bool:
        return self.reversed_at is not None


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
