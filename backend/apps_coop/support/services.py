"""Logique métier du support membre (fil unique).

Isolée des vues pour être testable et réutilisable (mobile + portail + admin).
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import SupportMessage, SupportThread


def get_or_create_thread(member) -> SupportThread:
    thread, _ = SupportThread.objects.get_or_create(member=member)
    return thread


@transaction.atomic
def post_member_message(member, body: str) -> SupportMessage:
    """Le membre écrit au support. Crée le fil au besoin."""
    thread = get_or_create_thread(member)
    msg = SupportMessage.objects.create(
        thread=thread,
        sender=SupportMessage.Sender.MEMBER,
        author=getattr(member, "user", None),
        body=body,
    )
    thread.last_message_at = timezone.now()
    thread.save(update_fields=["last_message_at", "updated_at"])
    return msg


@transaction.atomic
def post_staff_reply(thread: SupportThread, author, body: str) -> SupportMessage:
    """Le support répond. Notifie le membre (in-app + push best-effort)."""
    msg = SupportMessage.objects.create(
        thread=thread,
        sender=SupportMessage.Sender.STAFF,
        author=author,
        body=body,
    )
    thread.last_message_at = timezone.now()
    thread.save(update_fields=["last_message_at", "updated_at"])

    # Notification in-app + push (le push part si FCM est provisionné ; sinon
    # no-op silencieux — cf. apps_coop.notifications.push).
    user = getattr(thread.member, "user", None)
    if user is not None:
        try:
            from apps_coop.notifications.services import create_notification

            create_notification(
                user=user,
                type="support.reply",
                message=body[:180],
                lien="/support",
            )
        except Exception:  # noqa: BLE001 — la notif ne doit jamais casser la réponse
            pass
    return msg


def mark_read(thread: SupportThread, *, reader: str) -> int:
    """Marque comme lus les messages destinés à `reader` ('member' | 'staff').

    Un membre lit les messages du STAFF ; le staff lit les messages du MEMBRE.
    Retourne le nombre de messages basculés.
    """
    other = (
        SupportMessage.Sender.STAFF
        if reader == "member"
        else SupportMessage.Sender.MEMBER
    )
    return thread.messages.filter(sender=other, read_by_recipient=False).update(
        read_by_recipient=True
    )
