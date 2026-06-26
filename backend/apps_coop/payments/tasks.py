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
# as suspicious enough to actively poll it. Abaisse a 2 min pour la phase de
# test STK Push reel — en prod stable, repasser a 30 min pour limiter les
# appels Tara.
RECONCILE_AFTER = timedelta(minutes=2)

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

    import time

    summary = {
        "checked": 0, "valide": 0, "rejete": 0,
        "still_pending": 0, "timed_out": 0, "errors": 0, "rate_limited": 0,
    }

    # Tara rate-limit ~ 3 req/min en pratique. On espace les check_status
    # de 2 sec et on retry une fois si TOO_MANY_REQUESTS (sleep 25s).
    INTER_CALL_DELAY = 2.0
    RATE_LIMIT_RETRY_DELAY = 25.0

    for idx, payment in enumerate(base_qs):
        # 24 h elapsed → give up regardless of provider answer.
        if payment.gateway_initiated_at and payment.gateway_initiated_at <= timeout_threshold:
            with transaction.atomic():
                payment.statut = Payment.Statut.REJETE
                payment.motif_rejet = "Timeout — no confirmation within 24h."
                payment.save(update_fields=["statut", "motif_rejet", "updated_at"])
                summary["timed_out"] += 1
            continue

        # Sleep entre 2 appels Tara pour ne pas se faire throttler.
        if idx > 0:
            time.sleep(INTER_CALL_DELAY)

        summary["checked"] += 1
        try:
            provider = get_provider(payment.provider_code)
            current = provider.check_status(payment)
        except (ProviderError, ValueError) as exc:
            err_msg = str(exc)
            if "TOO_MANY_REQUESTS" in err_msg:
                # Retry une fois apres pause prolongee.
                logger.info(
                    "Tara throttle on Payment #%s, sleep %ss and retry",
                    payment.id, RATE_LIMIT_RETRY_DELAY,
                )
                time.sleep(RATE_LIMIT_RETRY_DELAY)
                try:
                    current = provider.check_status(payment)
                except (ProviderError, ValueError) as exc2:
                    logger.warning(
                        "Reconcile retry failed for Payment #%s: %s", payment.id, exc2,
                    )
                    summary["rate_limited"] += 1
                    continue
            else:
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


# ---------------------------------------------------------------------------
# O5 . Alerte admin si paiement coince trop longtemps
# ---------------------------------------------------------------------------

def alert_stuck_payments() -> dict:
    """Cron de supervision . envoie un email recap aux admins si des
    Payment restent EN_ATTENTE depuis plus de `payments.alert.stuck_after_minutes`
    (defaut 60 min).

    Indispensable pour detecter les pannes Tara silencieuses ou un bug du
    cron de reconciliation. Best-effort . erreur d'envoi ne fait pas
    planter le cron.

    Returns un dict {checked, alerted, recipients} pour le logging.
    """
    from django.core.mail import EmailMessage
    from django.conf import settings as dj_settings

    # Seuil tunable . defaut 60 min (paye depuis 1h mais toujours en_attente).
    try:
        from apps_coop.audit.services import get_int_setting
        threshold_minutes = get_int_setting(
            "payments.alert.stuck_after_minutes", 60,
        )
    except Exception:  # noqa: BLE001
        threshold_minutes = 60

    cutoff = timezone.now() - timedelta(minutes=threshold_minutes)
    stuck = (
        Payment.objects.filter(
            statut=Payment.Statut.EN_ATTENTE,
            source=Payment.Source.MOBILE_MONEY,
            gateway_initiated_at__lte=cutoff,
        )
        .select_related("member")
        .order_by("gateway_initiated_at")[:50]
    )
    summary = {"checked": stuck.count(), "alerted": 0, "recipients": 0}
    if stuck.count() == 0:
        return summary

    # Destinataires . liste tunable, fallback DEFAULT_FROM_EMAIL.
    try:
        from apps_coop.audit.services import get_str_setting
        recipients_raw = get_str_setting(
            "payments.alert.recipients",
            getattr(dj_settings, "CONTACT_NOTIFICATION_EMAIL", "")
            or getattr(dj_settings, "DEFAULT_FROM_EMAIL", ""),
        )
    except Exception:  # noqa: BLE001
        recipients_raw = getattr(
            dj_settings, "CONTACT_NOTIFICATION_EMAIL", "",
        ) or getattr(dj_settings, "DEFAULT_FROM_EMAIL", "")
    recipients = [r.strip() for r in (recipients_raw or "").split(",") if r.strip()]
    if not recipients:
        logger.warning(
            "alert_stuck_payments . %d payments bloques mais aucun destinataire",
            stuck.count(),
        )
        return summary

    # Composition email simple (HTML inline, pas besoin de template DB).
    rows_html = []
    for p in stuck:
        member_label = (
            f"{p.member.numero_membre or '-'} {p.member.prenom or ''} {p.member.nom or ''}"
            if p.member else "(membre supprime)"
        )
        rows_html.append(
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;'>#{p.id}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;'>{member_label}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;font-family:monospace;font-size:12px;'>{p.type}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;text-align:right;'>{p.montant} XAF</td>"
            f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;font-size:12px;'>{p.gateway_initiated_at}</td>"
            f"</tr>",
        )
    body = (
        '<!DOCTYPE html><html><body style="font-family:Inter,Arial,sans-serif;max-width:760px;margin:auto;padding:24px;">'
        f'<h1 style="color:#b91c1c;">{stuck.count()} paiement(s) bloque(s) depuis plus de {threshold_minutes} min</h1>'
        '<p>Le cron de reconciliation Tara n\'a pas reussi a clore ces paiements. '
        'Verifie que :</p>'
        '<ul><li>Tara ne renvoie pas une erreur 5xx persistante</li>'
        '<li>Le webhook arrive bien (logs gunicorn /payments/webhook/)</li>'
        '<li>Le worker django_q tourne (docker ps gathe-finance-prod-qcluster-1)</li></ul>'
        '<table style="border-collapse:collapse;width:100%;margin:18px 0;font-size:14px;">'
        '<thead><tr style="background:#f1f5f9;text-align:left;">'
        '<th style="padding:8px;">ID</th><th style="padding:8px;">Membre</th>'
        '<th style="padding:8px;">Type</th><th style="padding:8px;text-align:right;">Montant</th>'
        '<th style="padding:8px;">Initie le</th></tr></thead><tbody>'
        + "".join(rows_html) +
        '</tbody></table>'
        '<p style="color:#64748b;font-size:13px;">Verifie manuellement avec : '
        '<code>python manage.py reconcile_payments --payment-id &lt;ID&gt;</code></p>'
        '</body></html>'
    )
    try:
        msg = EmailMessage(
            subject=f"[Gathe] {stuck.count()} paiement(s) bloque(s) Tara",
            body=body,
            from_email=getattr(dj_settings, "DEFAULT_FROM_EMAIL", "noreply@horus-lab.com"),
            to=recipients,
        )
        msg.content_subtype = "html"
        msg.send(fail_silently=False)
        summary["alerted"] = stuck.count()
        summary["recipients"] = len(recipients)
        logger.warning(
            "alert_stuck_payments . envoye a %s, %d payments listes",
            recipients, stuck.count(),
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "alert_stuck_payments . echec envoi email a %s", recipients,
        )
    return summary
