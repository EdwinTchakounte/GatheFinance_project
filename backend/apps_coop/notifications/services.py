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
import mimetypes
import re
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import EmailLog, EmailTemplate, Notification


logger = logging.getLogger(__name__)

# Logo embarqué via Content-ID (cid:gathe-logo) — référencé depuis le HTML
# layout. Compatible Gmail/Outlook/Apple Mail. Chargé une fois en mémoire.
_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"
_LOGO_CID = "gathe-logo"


def _render(text: str, context: dict) -> str:
    try:
        return text.format(**context)
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("Email template rendering failed (%s) — using raw text", exc)
        return text


# ---------------------------------------------------------------------------
# Layout HTML — wrapper visuel pour tous les emails transactionnels.
# ---------------------------------------------------------------------------
#
# Pourquoi un layout en dur dans services.py et pas un template Django ?
#
# Les emails HTML demandent **CSS inline** + structure en **tables** pour
# fonctionner dans Gmail, Outlook, Apple Mail. Garder le wrapper proche
# du sender évite la confusion (un seul endroit où modifier le design).
# Les corps_html en DB restent simples (<p>, <ul>, <a>) — c'est le
# wrapper qui apporte le brand visuel (header aurore + logo + card +
# footer).
#
# Le logo est référencé via ``cid:gathe-logo`` ; on l'attache comme
# MIMEImage avec ``Content-Disposition: inline`` plus bas dans send_template.

_EMAIL_LAYOUT = """\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#F2EFE8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#0F172A;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F2EFE8;padding:32px 16px;">
  <tr>
    <td align="center">
      <!-- Card 600px -->
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background:#FFFFFF;border-radius:18px;overflow:hidden;box-shadow:0 6px 28px rgba(15,23,42,0.08);">

        <!-- Header aurore (teal → bleu → navy) — wordmark élégant. Si
             ``settings.EMAIL_LOGO_URL`` est défini (URL publique), une
             image remplace le bloc texte côté wordmark (cf. _wrap_layout). -->
        <tr>
          <td style="background-color:#1E3A8A;background-image:linear-gradient(135deg,#00B894 0%,#1E40AF 55%,#1E3A8A 100%);padding:44px 32px 36px 32px;text-align:center;">
            {logo_or_wordmark}
            <div style="color:rgba(255,255,255,0.82);font-size:11px;margin-top:8px;letter-spacing:0.16em;text-transform:uppercase;">Coopérative d'épargne &amp; de crédit</div>
          </td>
        </tr>

        <!-- Eyebrow doux sous le header (optionnel) -->
        <tr>
          <td style="background:#FFFFFF;padding:10px 0 0 0;text-align:center;">
            <div style="display:inline-block;background:#ECFDF5;color:#047857;padding:5px 14px;border-radius:999px;font-size:11px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;">{eyebrow}</div>
          </td>
        </tr>

        <!-- Corps -->
        <tr>
          <td style="padding:24px 36px 12px 36px;color:#0F172A;font-size:15px;line-height:1.65;">
            {body}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:22px 32px 28px 32px;border-top:1px solid #E5E7EB;background:#FAFAF8;text-align:center;">
            <p style="margin:0 0 6px 0;color:#374151;font-size:12px;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;">GATHE Finance</p>
            <p style="margin:0;color:#6B7280;font-size:12px;line-height:1.7;">
              Akwa Bercy, Douala — Cameroun<br>
              <a href="mailto:contact@gathe-finance.com" style="color:#1E3A8A;text-decoration:none;">contact@gathe-finance.com</a> · <a href="https://gathe-finance.horus-lab.com" style="color:#1E3A8A;text-decoration:none;">gathe-finance.com</a>
            </p>
            <p style="margin:14px 0 0 0;color:#9CA3AF;font-size:11px;">
              © 2026 GATHE Finance — Tous droits réservés.<br>
              Cet email vous est envoyé suite à une action sur votre compte.
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""


def _eyebrow_from_code(code: str) -> str:
    """Petit label thématique en haut du corps. Sans heuristique exotique :
    on prend le premier segment du code (avant le point) et on humanise."""
    head = (code or "").split(".", 1)[0]
    return {
        "member": "Adhésion",
        "savings": "Épargne",
        "loan": "Crédit",
        "loan_request": "Demande de crédit",
        "loan_renewal": "Reconduction",
        "withdrawal": "Retrait",
        "booklet": "Carnet",
        "auth": "Sécurité",
        "announcement": "Annonce",
    }.get(head, "Notification")


def _wrap_layout(subject: str, inner_html: str, *, eyebrow: str = "") -> str:
    """Enrobe le ``corps_html`` dans le layout brand (header + footer +
    typographie). Échappe le ``subject`` pour l'attribut <title>.

    Si ``settings.EMAIL_LOGO_URL`` est défini (URL publique HTTPS d'une
    image servie depuis la vitrine ou un CDN), on l'affiche dans le
    header. Sinon, on retombe sur un wordmark texte stylé "GATHE Finance"
    en serif blanc — propre et compatible toutes inboxes sans dépendre
    d'un fichier hébergé.
    """
    safe_subject = re.sub(r"[<>&\"]", " ", subject or "GATHE Finance").strip()
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "") or ""
    if logo_url:
        logo_or_wordmark = (
            f'<img src="{logo_url}" alt="GATHE Finance" width="160" height="auto" '
            'style="display:block;margin:0 auto;max-width:60%;height:auto;'
            'filter:drop-shadow(0 4px 12px rgba(0,0,0,0.25));">'
        )
    else:
        logo_or_wordmark = (
            '<div style="color:#FFFFFF;font-family:Georgia,\'Times New Roman\',serif;'
            'font-size:30px;font-weight:600;letter-spacing:0.6px;line-height:1.15;">'
            'GATHE Finance</div>'
        )
    return _EMAIL_LAYOUT.format(
        subject=safe_subject,
        eyebrow=eyebrow or "Notification",
        body=inner_html,
        logo_or_wordmark=logo_or_wordmark,
    )


def _load_logo_attachment() -> MIMEImage | None:
    """Charge le logo PNG en mémoire pour l'attacher comme ``inline`` avec
    Content-ID ``gathe-logo``. ``None`` si le fichier manque (degrade
    silently — le client mail affichera juste un placeholder)."""
    try:
        data = _LOGO_PATH.read_bytes()
    except (OSError, FileNotFoundError) as exc:
        logger.warning("Logo email introuvable (%s) — fallback sans image", exc)
        return None
    mime, _ = mimetypes.guess_type(str(_LOGO_PATH))
    subtype = (mime or "image/png").split("/", 1)[-1]
    image = MIMEImage(data, _subtype=subtype)
    image.add_header("Content-ID", f"<{_LOGO_CID}>")
    image.add_header("Content-Disposition", "inline", filename=_LOGO_PATH.name)
    return image


def send_template(
    code: str,
    *,
    to: str,
    context: dict | None = None,
    member=None,
    attachments: list | None = None,
) -> EmailLog:
    """Render the template ``code`` with ``context`` and send to ``to``.

    ``attachments`` (optionnel) : liste de tuples ``(filename, content, mimetype)``
    transmis tels quels à ``EmailMessage.attach`` — p. ex. l'attestation
    d'adhésion jointe à l'e-mail de bienvenue. ``None`` = aucune pièce jointe.

    Returns the persisted ``EmailLog`` row (statut = ``envoye`` or ``echec``).
    Never raises — designed to be called from business hooks where audit
    failure must not crash the webhook chain.
    """
    ctx = context or {}
    # On distingue les deux cas (EXT-3) :
    #   - template absent  → vrai bug de configuration → ``logger.error``
    #   - template présent mais ``actif=False`` → kill-switch admin volontaire,
    #     on trace en audit pour preuve mais on ne crie pas.
    try:
        template = EmailTemplate.objects.get(code=code)
    except EmailTemplate.DoesNotExist:
        logger.error("EmailTemplate code=%r introuvable", code)
        return None  # type: ignore[return-value]
    if not template.actif:
        try:
            from apps_coop.audit.services import record as record_audit

            record_audit(
                action="notification.skipped",
                entite_type="EmailTemplate",
                entite_id=template.id,
                user=getattr(member, "user", None) if member else None,
                details={
                    "code": code,
                    "destinataire": to,
                    "reason": "template_inactive",
                },
            )
        except Exception:  # pragma: no cover — audit best-effort
            logger.exception("Audit du skip notification a échoué")
        logger.info(
            "send_template skipped: template code=%r is inactive (admin kill-switch)",
            code,
        )
        return None  # type: ignore[return-value]

    subject = _render(template.objet, ctx)
    body_html_raw = _render(template.corps_html, ctx)
    body_text = _render(template.corps_texte or "", ctx)

    # Enrobe le corps dans le layout brand (header aurore + logo CID + footer).
    body_html = _wrap_layout(
        subject,
        body_html_raw,
        eyebrow=_eyebrow_from_code(code),
    ) if body_html_raw else ""

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
        for att in attachments or []:
            # (filename, content, mimetype) — signature Django EmailMessage.attach.
            msg.attach(*att)
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
    sans forcément envoyer un email. Tente aussi un envoi **push** (best-effort,
    no-op tant que FCM n'est pas configuré — voir ``notifications.push``).
    """
    notif = Notification.objects.create(
        user=user,
        type=type,
        message=message,
        lien=lien,
    )
    try:
        from .push import send_push_to_user

        send_push_to_user(
            user, title="GATHE Finance", body=message, data={"type": type, "lien": lien}
        )
    except Exception:  # noqa: BLE001 — le push ne doit jamais casser le flux
        pass
    return notif


def broadcast_announcement(announcement) -> int:
    """Matérialise une ``Notification`` in-app par membre cible.

    Idempotent : appelée 2× pour la même annonce, ne re-crée pas de doublons
    (on filtre les users qui ont déjà une Notification avec lien = ``ann:<id>``).
    Retourne le nombre de notifications **créées** (pas le total cible).
    """
    from apps_coop.members.models import Member
    from .models import Announcement, Notification

    if announcement.audience == Announcement.Audience.ALL:
        members = Member.objects.exclude(user__isnull=True)
    elif announcement.audience == Announcement.Audience.ACTIFS:
        members = Member.objects.filter(statut=Member.Statut.ACTIF).exclude(
            user__isnull=True
        )
    elif announcement.audience == Announcement.Audience.SUSPENDUS:
        members = Member.objects.filter(statut=Member.Statut.SUSPENDU).exclude(
            user__isnull=True
        )
    elif announcement.audience == Announcement.Audience.SELECTION:
        ids = announcement.audience_member_ids or []
        members = Member.objects.filter(id__in=ids).exclude(user__isnull=True)
    else:
        members = Member.objects.none()

    tag = f"ann:{announcement.id}"
    already_notified_user_ids = set(
        Notification.objects.filter(lien=tag).values_list("user_id", flat=True)
    )

    to_create = []
    for m in members.select_related("user").only("user_id"):
        if m.user_id in already_notified_user_ids:
            continue
        # Le mobile dérive son `title` du `type` ("annonce" → "Annonce") ;
        # on préfixe donc le corps par le titre de l'annonce pour que celui-ci
        # reste visible côté membre. Format : "TITRE\n\nCORPS".
        body = (
            f"{announcement.titre}\n\n{announcement.corps}"
            if announcement.titre
            else announcement.corps
        )
        to_create.append(
            Notification(
                user_id=m.user_id,
                type="annonce",
                message=body,
                lien=announcement.lien or tag,
                lue=False,
            )
        )
    Notification.objects.bulk_create(to_create, batch_size=500)
    return len(to_create)


def _strip_html(html: str) -> str:
    """Tiny HTML → plain-text fallback (good enough for transactional emails)."""
    import re

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
