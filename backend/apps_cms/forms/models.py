"""Inbound form data.

Maps to the "DONNÉES ENTRANTES" category of conception/07. These rows are
read-only for editors in the Wagtail admin; they are created by the public form
endpoints (apps.forms.views) and trigger a Brevo notification + acknowledgement.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseSubmission(models.Model):
    name = models.CharField(_("Nom"), max_length=200)
    city = models.CharField(_("Ville"), max_length=160, blank=True)
    phone = models.CharField(_("Téléphone"), max_length=40, blank=True)
    email = models.EmailField(_("Adresse e-mail"))
    message = models.TextField(_("Message"), blank=True)
    language = models.CharField(_("Langue"), max_length=8, default="fr")
    submitted_at = models.DateTimeField(_("Reçu le"), auto_now_add=True)
    ip_address = models.GenericIPAddressField(_("Adresse IP"), null=True, blank=True)
    user_agent = models.CharField(_("Navigateur"), max_length=400, blank=True)
    internal_notes = models.TextField(_("Notes internes"), blank=True)

    class Meta:
        abstract = True
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.name} <{self.email}> — {self.submitted_at:%Y-%m-%d %H:%M}"


class ContactSubmission(BaseSubmission):
    class Status(models.TextChoices):
        NEW = "new", _("Nouveau")
        IN_PROGRESS = "in_progress", _("En traitement")
        DONE = "done", _("Traité")

    status = models.CharField(
        _("Statut"), max_length=20, choices=Status.choices, default=Status.NEW
    )

    class Meta(BaseSubmission.Meta):
        verbose_name = _("Message de contact")
        verbose_name_plural = _("Messages de contact")


class NewsletterSubscriber(models.Model):
    email = models.EmailField(_("Adresse e-mail"), unique=True)
    language = models.CharField(_("Langue"), max_length=8, default="fr")
    consent = models.BooleanField(_("Consentement"), default=True)
    source = models.CharField(_("Source"), max_length=120, blank=True)
    subscribed_at = models.DateTimeField(_("Inscrit le"), auto_now_add=True)
    is_active = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Inscrit newsletter")
        verbose_name_plural = _("Inscrits newsletter")
        ordering = ["-subscribed_at"]

    def __str__(self):
        return self.email
