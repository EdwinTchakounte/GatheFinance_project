"""Audit & system settings — every sensitive mutation gets one AuditLog row.

`AuditLog` is append-only by design: no UPDATE/DELETE views are exposed.
`AppSetting` holds key/value runtime config the admin can tweak from Django admin.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel


class AuditLog(models.Model):
    """Append-only ledger of sensitive admin/system actions."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64, db_index=True, help_text="e.g. 'loan.approve'")
    entite_type = models.CharField(max_length=64, db_index=True)
    entite_id = models.PositiveBigIntegerField(null=True, blank=True)
    details_json = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entite_type", "entite_id"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        verbose_name = "Entrée d'audit"
        verbose_name_plural = "Journal d'audit"

    def __str__(self) -> str:
        return f"{self.action} · {self.entite_type}#{self.entite_id}"


class AppSetting(TimestampedModel):
    """Runtime configuration — admin-editable without a code change."""

    cle = models.CharField(max_length=64, unique=True, db_index=True)
    valeur = models.CharField(max_length=512)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["cle"]
        verbose_name = "Paramètre système"
        verbose_name_plural = "Paramètres système"

    def __str__(self) -> str:
        return f"{self.cle} = {self.valeur}"


class CooperativeAsset(TimestampedModel):
    """Documents officiels de la coopérative — singleton (1 ligne, pk=1).

    Pour l'instant porte uniquement le **règlement intérieur (PDF)** qui est
    joint au mail de bienvenue UC1 (cf. ``_send_welcome_email``). L'admin met
    à jour le fichier via l'endpoint dédié :
    ``POST /api/v1/admin/cooperative-asset/reglement/`` (multipart).

    Pattern singleton : on récupère TOUJOURS la ligne via ``get_solo()`` —
    pas d'index, pas de pluriel.
    """

    reglement_interieur = models.FileField(
        upload_to="coop/assets/",
        null=True,
        blank=True,
        help_text=(
            "PDF du règlement intérieur — joint au mail de bienvenue UC1. "
            "Si vide, le mail part sans pièce jointe (attestation seule)."
        ),
    )
    reglement_uploaded_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reglement_uploaded_at = models.DateTimeField(null=True, blank=True)

    # Spécimen de carnet (PDF) — affiché en téléchargement sur la page
    # "Commander mon carnet" pour que le membre voie à quoi ressemble le
    # carnet avant de payer les frais.
    carnet_specimen = models.FileField(
        upload_to="coop/assets/",
        null=True,
        blank=True,
        help_text=(
            "PDF spécimen du carnet de cotisations — affiché sur la page "
            "Commander carnet (mobile + portail) pour pré-visualisation."
        ),
    )
    carnet_specimen_uploaded_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    carnet_specimen_uploaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Asset coopérative"
        verbose_name_plural = "Assets coopérative"

    def __str__(self) -> str:
        return "Assets coopérative (singleton)"

    @classmethod
    def get_solo(cls) -> "CooperativeAsset":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# --- Invalidation du cache des AppSetting ----------------------------------
# Le config-cache (apps_coop.audit.services._read_setting_raw) mémoïse chaque
# valeur ; on la purge dès qu'un admin l'édite/supprime pour une propagation
# immédiate (sur le worker éditeur ; les autres suivent via le TTL).
from django.db.models.signals import post_delete, post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver([post_save, post_delete], sender=AppSetting)
def _invalidate_appsetting_cache(sender, instance, **kwargs):  # noqa: ANN001, ARG001, ANN201
    from django.core.cache import cache

    from .services import setting_cache_key

    cache.delete(setting_cache_key(instance.cle))
