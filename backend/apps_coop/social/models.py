"""Modeles d'interactions sociales — likes & commentaires.

On utilise un GenericForeignKey pour brancher reactions et commentaires
indistinctement sur n'importe quel "contenu" (article CMS Wagtail ou
MicrocreditCampaign). Cela evite d'avoir des tables redondantes par type
de contenu et facilite l'ajout d'autres cibles a l'avenir (annonces,
documents, etc.).

Choix d'implementation :
- ContentReaction = like simple (binaire, on/off via toggle). Unique
  (user, content_type, object_id) — un membre ne peut liker qu'une fois
  un meme contenu.
- ContentComment = commentaire texte court, masquable par staff (jamais
  supprime de la DB pour l'audit, ce qui distingue le masquage de la
  suppression-membre qui, elle, supprime l'objet).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps_coop.common import TimestampedModel


class ContentReaction(models.Model):
    """Reaction "like" sur un contenu (article ou campagne).

    Modelise un like simple. Pour ajouter d'autres types (love, etc.) il
    suffirait d'ajouter un champ `kind` indexe ; ce n'est pas demande dans
    ce premier jet donc on garde un schema minimal.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_reactions",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Reaction (like)"
        verbose_name_plural = "Reactions (likes)"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="social_reaction_unique_per_target",
            ),
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self) -> str:  # pragma: no cover — debug only
        return f"like by {self.user_id} on {self.content_type_id}:{self.object_id}"


class ContentComment(TimestampedModel):
    """Commentaire (texte court) sur un contenu (article ou campagne).

    `hidden=True` est un soft-hide pose par le staff via le dashboard admin.
    Le contenu reste en DB pour audit (qui, quand, pourquoi). Cote API
    publique on renvoie le commentaire avec body remplace par un placeholder
    "[Commentaire masque]" et `hidden=True` ; l'UI rend en italique grise.
    Le staff voit le vrai body avec un flag `hidden` distinct.
    """

    MAX_BODY_LEN = 1000

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_comments",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    body = models.TextField(max_length=MAX_BODY_LEN)

    # Masquage (soft-hide par staff).
    hidden = models.BooleanField(default=False, db_index=True)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments_hidden",
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"
        indexes = [
            models.Index(fields=["content_type", "object_id", "-created_at"]),
            models.Index(fields=["hidden", "-created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover — debug only
        return f"comment #{self.pk} by {self.user_id}"
