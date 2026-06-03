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


# ---------------------------------------------------------------------------
# EXT-5 — Moteur d'événements métier (définition ↔ exécution dissociées).
# ---------------------------------------------------------------------------
#
# Idée : chaque action métier (adhésion approuvée, retard détecté, retrait
# demandé…) émet un **événement nommé** via ``emit_event(code, …)``. La
# décision « envoyer quoi à qui » vit en base (EventConfig + EventHook), pas
# dans le code appelant. Un admin peut couper / activer / brancher de
# nouvelles actions sans déploiement.


class EventConfig(TimestampedModel):
    """Catalogue des événements métier émis par l'application.

    Chaque ligne décrit **un type d'événement** (ex. ``loan.installment_overdue``)
    et son comportement par défaut. Les *actions* à exécuter quand l'événement
    arrive sont définies dans la table liée ``EventHook``.

    Le ``status`` pilote l'effet du kill-switch admin :
      - ``REQUIRED`` : toujours actif, l'admin **ne peut pas** couper
        (réservé aux actes à valeur juridique : activation, retard, contentieux).
      - ``OPTIONAL`` : actif si ``active=True``, désactivable.
      - ``BLOCKED`` : forcé OFF (kill-switch immédiat).

    ``sensitive`` est un flag d'UX : l'admin doit confirmer dans une modale
    avant de désactiver/bloquer (pas un verrou — l'admin reste souverain).
    """

    class Status(models.TextChoices):
        REQUIRED = "REQUIRED", "Requis (toujours actif)"
        OPTIONAL = "OPTIONAL", "Optionnel (activable)"
        BLOCKED = "BLOCKED", "Bloqué (kill-switch)"

    code = models.CharField(max_length=64, unique=True, db_index=True)
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPTIONAL,
        db_index=True,
    )
    active = models.BooleanField(
        default=True,
        help_text="Effectif uniquement quand status=OPTIONAL.",
    )
    sensitive = models.BooleanField(
        default=False,
        help_text="Si vrai, l'admin doit confirmer avant de couper "
        "(événement à impact légal ou opérationnel fort).",
    )

    class Meta:
        ordering = ["code"]
        verbose_name = "Configuration d'événement"
        verbose_name_plural = "Configurations d'événements"

    def __str__(self) -> str:
        return f"{self.code} · {self.status}"

    @property
    def is_effective(self) -> bool:
        """Faut-il exécuter les hooks de cet événement ?

        REQUIRED → toujours ; OPTIONAL → selon ``active`` ; BLOCKED → jamais.
        """
        if self.status == self.Status.BLOCKED:
            return False
        if self.status == self.Status.REQUIRED:
            return True
        return bool(self.active)


class EventHook(TimestampedModel):
    """Action à exécuter lorsqu'un événement est émis.

    Plusieurs hooks peuvent être branchés sur un même événement (ex. envoyer
    un e-mail au membre **et** créer une notification in-app — déjà géré par
    ``send_template`` aujourd'hui, donc un seul hook EMAIL suffit en général).
    """

    class ActionType(models.TextChoices):
        EMAIL = "EMAIL", "E-mail (template)"
        AUDIT_ONLY = "AUDIT_ONLY", "Audit seulement (silencieux)"

    event = models.ForeignKey(
        EventConfig,
        on_delete=models.CASCADE,
        related_name="hooks",
    )
    action_type = models.CharField(
        max_length=16,
        choices=ActionType.choices,
        default=ActionType.EMAIL,
    )
    target_template_code = models.CharField(
        max_length=64,
        blank=True,
        help_text="Code EmailTemplate à rendre. Si vide, on utilise event.code.",
    )
    active = models.BooleanField(default=True, db_index=True)
    ordering = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["event", "ordering"]
        verbose_name = "Hook d'événement"
        verbose_name_plural = "Hooks d'événements"

    def __str__(self) -> str:
        return f"{self.event.code} → {self.action_type}"
