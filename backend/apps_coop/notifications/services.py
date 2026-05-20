"""Email sending — single entry point ``send_template``.

  - Templates live in the ``EmailTemplate`` table (admin-editable).
  - Each send writes an ``EmailLog`` row for traceability.
  - In dev, ``EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend``
    prints the email to stdout instead of hitting Brevo. Switch the backend
    via env var in ``backend/.env``.
  - ``str.format(**context)`` is used as the templating engine — minimal,
    pas de Jinja, pas d'exécution arbitraire. Sufficient for our short
    transactional emails.
  - Never raises : a failed send is logged + ``EmailLog.statut=echec``.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import EmailLog, EmailTemplate, Notification


logger = logging.getLogger(__name__)


def _render(text: str, context: dict) -> str:
    try:
        return text.format(**context)
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("Email template rendering failed (%s) — using raw text", exc)
        return text


def send_template(
    code: str,
    *,
    to: str,
    context: dict | None = None,
    member=None,
) -> EmailLog:
    """Render the template ``code`` with ``context`` and send to ``to``.

    Returns the persisted ``EmailLog`` row (statut = ``envoye`` or ``echec``).
    Never raises — designed to be called from business hooks where audit
    failure must not crash the webhook chain.
    """
    ctx = context or {}
    try:
        template = EmailTemplate.objects.get(code=code, actif=True)
    except EmailTemplate.DoesNotExist:
        logger.error("EmailTemplate code=%r introuvable ou inactif", code)
        # Pas d'EmailLog si le template lui-même est manquant — l'erreur est dans le log.
        return None  # type: ignore[return-value]

    subject = _render(template.objet, ctx)
    body_html = _render(template.corps_html, ctx)
    body_text = _render(template.corps_texte or "", ctx)

    log = EmailLog.objects.create(
        template=template,
        destinataire=to,
        member=member,
        objet=subject,
        statut=EmailLog.Statut.EN_ATTENTE,
    )
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text or _strip_html(body_html),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        if body_html:
            msg.attach_alternative(body_html, "text/html")
        msg.send(fail_silently=False)
        log.statut = EmailLog.Statut.ENVOYE
        log.sent_at = timezone.now()
        log.save(update_fields=["statut", "sent_at", "updated_at"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("Email send failed for template=%s to=%s", code, to)
        log.statut = EmailLog.Statut.ECHEC
        log.erreur = str(exc)[:1000]
        log.save(update_fields=["statut", "erreur", "updated_at"])

    # Miroir in-app : crée une Notification persistée pour l'affichage portail
    # / mobile, indépendamment du succès de l'email. On ne le fait que si on
    # connaît le membre destinataire (sinon on ne sait pas à quel user lier).
    if member is not None and getattr(member, "user_id", None):
        try:
            create_notification(
                user=member.user,
                type=code,
                message=subject,
                lien=ctx.get("portal_url", ""),
            )
        except Exception:  # noqa: BLE001
            logger.warning("in-app notification mirror failed for %s", code, exc_info=True)
    return log


def create_notification(*, user, type: str, message: str, lien: str = "") -> Notification:
    """Crée une notification in-app pour ``user``.

    Helper réutilisable directement par les hooks métier qui veulent notifier
    sans forcément envoyer un email.
    """
    return Notification.objects.create(
        user=user,
        type=type,
        message=message,
        lien=lien,
    )


def _strip_html(html: str) -> str:
    """Tiny HTML → plain-text fallback (good enough for transactional emails)."""
    import re

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
