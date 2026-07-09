"""E-mail notifications pour les formulaires entrants (vitrine).

Réutilise le layout brand (header aurore + footer) défini dans
``apps_coop.notifications.services._wrap_layout`` et les blocs HTML
``apps_coop.notifications.email_blocks`` pour rester cohérent avec les
emails transactionnels (welcome, dépôt, crédit, etc.).
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import gettext as _
from django.utils.translation import override

from apps_coop.notifications import email_blocks as B
from apps_coop.notifications.services import _wrap_layout


def _send(
    subject: str,
    to: list[str],
    text_body: str,
    html_body: str | None = None,
    reply_to: list[str] | None = None,
) -> None:
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to or None,
    )
    if html_body:
        msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def notify_team(kind: str, data: dict) -> None:
    """Email l'inbox interne avec les détails de la soumission vitrine."""
    label = {
        "contact": _("Nouveau message de contact"),
        "membership": _("Nouvelle demande d'adhésion"),
    }.get(kind, _("Nouvelle soumission"))
    subject = f"[GATHE Finance] {label}"

    text_body = "\n".join([
        f"{label}",
        "",
        f"Nom        : {data.get('name', '')}",
        f"Ville      : {data.get('city', '')}",
        f"Téléphone  : {data.get('phone', '')}",
        f"E-mail     : {data.get('email', '')}",
        f"Langue     : {data.get('language', 'fr')}",
        "",
        "Message :",
        data.get("message", "") or "(aucun)",
    ])

    inner = "".join([
        B.title(label),
        B.lead(
            f"Une nouvelle soumission de type <strong>{kind}</strong> vient "
            "d'arriver. Voici le résumé."
        ),
        B.info_card([
            ("Nom", data.get("name", "—") or "—"),
            ("Email", data.get("email", "—") or "—"),
            ("Téléphone", data.get("phone", "—") or "—"),
            ("Ville", data.get("city", "—") or "—"),
            ("Langue", data.get("language", "fr") or "fr"),
        ], tone="info"),
        B.p(
            f"<strong>Message :</strong><br>"
            f"{data.get('message', '') or '<em>(aucun)</em>'}"
        ),
        B.cta_secondary(
            "Ouvrir le dashboard",
            f"{getattr(settings, 'FRONTEND_PUBLIC_URL', '')}/admin/membership-requests",
        ),
    ])
    html_body = _wrap_layout(subject, inner, eyebrow="Vitrine")

    _send(
        subject=subject,
        to=[settings.CONTACT_NOTIFICATION_EMAIL],
        text_body=text_body,
        html_body=html_body,
        reply_to=[data["email"]] if data.get("email") else None,
    )


def acknowledge(kind: str, data: dict) -> None:
    """Email d'accusé de réception au visiteur — design brand cohérent."""
    lang = (data.get("language") or "fr")[:2]
    name = (data.get("name") or "").strip() or "membre"

    with override(lang):
        if kind == "membership":
            subject = _("Votre demande d'adhésion à GATHE Finance a bien été reçue")
            heading = _("Demande d'adhésion reçue")
            body_lead = _(
                "Nous avons bien reçu votre demande pour devenir membre de "
                "GATHE Finance. Notre comité va examiner votre dossier sous "
                "7 jours ouvrés."
            )
            next_steps = _(
                "Vous serez recontacté(e) par email dès qu'une décision sera "
                "prise. Préparez vos pièces (CNI, photo, plan de localisation) "
                "pour l'entretien d'admission, conformément à l'Article 3 du "
                "Règlement."
            )
            text_body = (
                f"Bonjour {name},\n\n"
                f"{body_lead}\n\n{next_steps}\n\n"
                "Cordialement,\nL'équipe GATHE Finance"
            )
        else:
            subject = _("Nous avons bien reçu votre message")
            heading = _("Message bien reçu")
            body_lead = _(
                "Merci de nous avoir contactés. Votre message a bien été "
                "transmis à notre équipe."
            )
            next_steps = _(
                "Nous vous répondrons dans les meilleurs délais, généralement "
                "sous 24 à 48 heures ouvrées."
            )
            text_body = (
                f"Bonjour {name},\n\n"
                f"{body_lead}\n\n{next_steps}\n\n"
                "Cordialement,\nL'équipe GATHE Finance"
            )

    inner = "".join([
        B.hi(name),
        B.title(heading),
        B.lead(body_lead),
        B.callout(next_steps, tone="info"),
        B.cta_secondary(
            _("Visiter notre site"),
            getattr(settings, "FRONTEND_PUBLIC_URL", "https://gathe-finance.horus-lab.com"),
        ),
        B.closing(),
    ])
    html_body = _wrap_layout(subject, inner, eyebrow="Vitrine")

    if data.get("email"):
        _send(
            subject=subject,
            to=[data["email"]],
            text_body=text_body,
            html_body=html_body,
        )
