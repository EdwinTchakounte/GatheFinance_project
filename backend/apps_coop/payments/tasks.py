"""Background tasks for the payments domain.

For now these are plain functions you can run via ``python manage.py shell`` or
hook into Django's ``django-q2`` / Celery later. The orchestrator (cron driver)
gets wired in a follow-up task — keeping it out of here means we don't depend
on a broker for the dev environment.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Payment
from .providers import get_provider
from .providers.base import ProviderError
from .services import handle_webhook_event


logger = logging.getLogger(__name__)


# How long we wait after gateway init before considering the provider's silence
# as suspicious enough to actively poll it.
RECONCILE_AFTER = timedelta(minutes=30)

# How long we wait before giving up entirely on a pending payment.
GIVE_UP_AFTER = timedelta(hours=24)


def reconcile_pending_payments(*, batch_size: int = 100) -> dict:
    """Hourly task — for every Payment stuck in ``en_attente`` past the
    ``RECONCILE_AFTER`` threshold, ask the provider for its current status.

    Returns a summary dict for logging / alerting.
    """
    now = timezone.now()
    stale_threshold = now - RECONCILE_AFTER
    timeout_threshold = now - GIVE_UP_AFTER

    base_qs = (
        Payment.objects.filter(
            statut=Payment.Statut.EN_ATTENTE,
            source=Payment.Source.MOBILE_MONEY,
            gateway_initiated_at__lte=stale_threshold,
        )
        .exclude(provider_code="")
        .order_by("gateway_initiated_at")[:batch_size]
    )

    summary = {"checked": 0, "valide": 0, "rejete": 0, "still_pending": 0, "timed_out": 0, "errors": 0}

    for payment in base_qs:
        # 24 h elapsed → give up regardless of provider answer.
        if payment.gateway_initiated_at and payment.gateway_initiated_at <= timeout_threshold:
            with transaction.atomic():
                payment.statut = Payment.Statut.REJETE
                payment.motif_rejet = "Timeout — no confirmation within 24h."
                payment.save(update_fields=["statut", "motif_rejet", "updated_at"])
                summary["timed_out"] += 1
            continue

        summary["checked"] += 1
        try:
            provider = get_provider(payment.provider_code)
            current = provider.check_status(payment)
        except (ProviderError, ValueError) as exc:
            logger.warning("Reconcile failed for Payment #%s: %s", payment.id, exc)
            summary["errors"] += 1
            continue

        if current == "valide":
            try:
                handle_webhook_event(payment.idempotency_key, "valide")
                summary["valide"] += 1
            except Exception:  # noqa: BLE001 — best-effort, keep iterating
                logger.exception("handle_webhook_event failed for Payment #%s", payment.id)
                summary["errors"] += 1
        elif current == "rejete":
            try:
                handle_webhook_event(payment.idempotency_key, "rejete")
                summary["rejete"] += 1
            except Exception:  # noqa: BLE001
                logger.exception("handle_webhook_event failed for Payment #%s", payment.id)
                summary["errors"] += 1
        else:
            summary["still_pending"] += 1

    logger.info("reconcile_pending_payments summary=%s", summary)
    return summary


def reconcile_pending_payments_scheduled() -> dict:
    """Schedule-friendly wrapper — django-q2 needs a zero-arg callable.

    Uses the default ``batch_size`` from ``reconcile_pending_payments``.
    """
    return reconcile_pending_payments()
