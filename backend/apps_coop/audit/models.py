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
