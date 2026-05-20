"""E-mail notifications for inbound forms (sent via Brevo SMTP).

Uses Django's templated e-mail; the SMTP backend/credentials come from settings
(see config/settings/base.py). Templates live in apps/forms/templates/forms/email/.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import gettext as _
from django.utils.translation import override


def _send(subject: str, to: list[str], text_body: str, reply_to: list[str] | None = None) -> None:
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to or None,
    )
    msg.send(fail_silently=False)


def notify_team(kind: str, data: dict) -> None:
    """E-mail the Gathe Finance inbox about a new submission."""
    label = {"contact": _("Nouveau message de contact"), "membership": _("Nouvelle demande d'adhésion")}.get(
        kind, _("Nouvelle soumission")
    )
    lines = [
        f"{label}",
        "",
        f"Nom        : {data.get('name', '')}",
        f"Ville      : {data.get('city', '')}",
        f"Téléphone  : {data.get('phone', '')}",
        f"E-mail     : {data.get('email', '')}",
        f"Langue     : {data.get('language', 'fr')}",
        "",
        "Message :",
        data.get("message", ""),
    ]
    _send(
        subject=f"[Gathe Finance] {label}",
        to=[settings.CONTACT_NOTIFICATION_EMAIL],
        text_body="\n".join(lines),
        reply_to=[data["email"]] if data.get("email") else None,
    )


def acknowledge(kind: str, data: dict) -> None:
    """Send the visitor a confirmation e-mail in their own language."""
    lang = (data.get("language") or "fr")[:2]
    with override(lang):
        if kind == "membership":
            subject = _("Votre demande d'adhésion à Gathe Finance a bien été reçue")
            body = _(
                "Bonjour %(name)s,\n\n"
                "Nous avons bien reçu votre demande pour devenir membre de Gathe Finance. "
                "Notre équipe vous recontactera prochainement.\n\n"
                "Cordialement,\nL'équipe Gathe Finance"
            ) % {"name": data.get("name", "")}
        else:
            subject = _("Nous avons bien reçu votre message")
            body = _(
                "Bonjour %(name)s,\n\n"
                "Merci de nous avoir contactés. Votre message a bien été transmis à notre équipe, "
                "qui vous répondra dans les meilleurs délais.\n\n"
                "Cordialement,\nL'équipe Gathe Finance"
            ) % {"name": data.get("name", "")}
    if data.get("email"):
        _send(subject=subject, to=[data["email"]], text_body=body)
