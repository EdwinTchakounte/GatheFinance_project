"""Notifications domain — email templates, send log, in-app notifications.

Email templates live in the DB so the admin can edit subject/body without a
deploy. Sending is done via Django's email backend; SMS / WhatsApp providers
will plug in later via the same `Notification` row + a `channel` enum extension.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel


class EmailTemplate(TimestampedModel):
    """One row per business event we email about (welcome, payment receipt, …)."""

    code = models.CharField(max_length=64, unique=True, db_index=True)
    objet = models.CharField(max_length=200)
    corps_html = models.TextField()
    corps_texte = models.TextField(blank=True, help_text="Fallback for clients that block HTML.")
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text="Declared variables (list of strings) for editor validation.",
    )
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Template d'email"
        verbose_name_plural = "Templates d'emails"

    def __str__(self) -> str:
        return self.code


class EmailLog(TimestampedModel):
    """Audit trail of every email we attempted to send."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        ENVOYE = "envoye", "Envoyé"
        ECHEC = "echec", "Échec"

    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.PROTECT,
        related_name="logs",
        to_field="code",
        db_column="template_code",
    )
    destinataire = models.EmailField()
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
    )
    objet = models.CharField(max_length=200)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE, db_index=True)
    erreur = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Email envoyé"
        verbose_name_plural = "Emails envoyés"

    def __str__(self) -> str:
        return f"{self.template_id} → {self.destinataire} ({self.statut})"


class Notification(TimestampedModel):
    """In-app notification displayed in the user's portal/dashboard."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=64, help_text="Free-form key, e.g. 'payment.confirmed'.")
    message = models.TextField()
    lien = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional internal link to the related resource.",
    )
    lue = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "lue", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.type} → {self.user_id}"
