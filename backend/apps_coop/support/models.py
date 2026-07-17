"""Support membre — messagerie **fil unique** membre ↔ support.

Un seul fil de discussion continu par membre (pas de tickets/sujets). Le membre
laisse des messages ; le support répond dans le même fil, quand il veut. Chaque
réponse du support déclenche une notification in-app + push (cf. views).

Pattern inspiré de ``apps_coop.social`` (parent/reply + notify), mais dédié à la
relation 1:1 membre↔coopérative plutôt qu'aux commentaires sur contenu.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel


class SupportThread(TimestampedModel):
    """Fil de support d'un membre (singleton par membre)."""

    member = models.OneToOneField(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="support_thread",
    )
    # Dénormalisé pour trier la boîte de réception admin sans agrégat coûteux.
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-last_message_at", "-created_at"]

    def __str__(self) -> str:  # pragma: no cover - debug repr
        return f"Support · {self.member.numero_membre}"

    def unread_for_member(self) -> int:
        """Messages du support pas encore lus par le membre."""
        return self.messages.filter(
            sender=SupportMessage.Sender.STAFF, read_by_recipient=False
        ).count()

    def unread_for_staff(self) -> int:
        """Messages du membre pas encore lus par le support."""
        return self.messages.filter(
            sender=SupportMessage.Sender.MEMBER, read_by_recipient=False
        ).count()


class SupportMessage(TimestampedModel):
    """Un message dans le fil de support (membre ou support)."""

    class Sender(models.TextChoices):
        MEMBER = "member", "Membre"
        STAFF = "staff", "Support"

    thread = models.ForeignKey(
        SupportThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField(max_length=8, choices=Sender.choices)
    # Auteur réel (utilisateur staff qui a répondu, ou user du membre). Nullable
    # pour survivre à la suppression d'un compte staff.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    body = models.TextField(max_length=4000)
    # `True` dès que le destinataire (l'autre partie) a ouvert le fil.
    read_by_recipient = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "sender", "read_by_recipient"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug repr
        return f"{self.get_sender_display()} · {self.body[:32]}"
