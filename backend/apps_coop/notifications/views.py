"""Notifications API — member-facing in-app notifications.

  - GET  /api/v1/notifications/            → liste des notifs du membre connecté
  - POST /api/v1/notifications/<id>/read/  → marque une notif comme lue
  - POST /api/v1/notifications/read-all/   → marque toutes comme lues

Toutes réservées au membre connecté (chaque user ne voit que ses notifs).
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Announcement, Notification
from .serializers import AnnouncementMemberSerializer, NotificationReadSerializer


@extend_schema(
    tags=["notifications"],
    summary="Liste des notifications du membre connecté",
    description=(
        "Renvoie les notifications in-app de l'utilisateur, les plus récentes "
        "d'abord. Paramètre optionnel `?unread=1` pour ne renvoyer que les "
        "non-lues."
    ),
    responses=NotificationReadSerializer(many=True),
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    qs = Notification.objects.filter(user=request.user)
    if request.query_params.get("unread") in ("1", "true", "True"):
        qs = qs.filter(lue=False)
    qs = qs[:100]  # garde-fou : on ne renvoie pas un historique infini
    unread_count = Notification.objects.filter(user=request.user, lue=False).count()
    return Response(
        {
            "results": NotificationReadSerializer(qs, many=True).data,
            "unread_count": unread_count,
        }
    )


@extend_schema(
    tags=["notifications"],
    summary="Liste des annonces destinées au membre connecté",
    description=(
        "Renvoie les annonces broadcast ciblant le membre (audience + non "
        "expirées), avec le corps complet et l'URL de la pièce jointe image. "
        "Sert à l'onglet « Annonces » mobile/portail (lecture détaillée)."
    ),
    responses=AnnouncementMemberSerializer(many=True),
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_my_announcements(request):
    member = getattr(request.user, "member", None)
    now = timezone.now()

    # Audience : l'annonce touche le membre si elle est « pour tous », ou pour
    # son statut (actif/suspendu), ou s'il figure dans la sélection nominative.
    audience_q = Q(audience=Announcement.Audience.ALL)
    if member is not None:
        statut = getattr(member, "statut", None)
        if statut == member.Statut.ACTIF:
            audience_q |= Q(audience=Announcement.Audience.ACTIFS)
        elif statut == member.Statut.SUSPENDU:
            audience_q |= Q(audience=Announcement.Audience.SUSPENDUS)
        audience_q |= Q(
            audience=Announcement.Audience.SELECTION,
            audience_member_ids__contains=member.id,
        )

    qs = (
        Announcement.objects.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .filter(audience_q)
        .order_by("-published_at", "-created_at")[:100]
    )
    data = AnnouncementMemberSerializer(
        qs, many=True, context={"request": request}
    ).data
    return Response({"results": data})


@extend_schema(
    tags=["notifications"],
    summary="Marquer une notification comme lue",
    responses={200: NotificationReadSerializer, 404: None},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_read(request, pk: int):
    try:
        notif = Notification.objects.get(pk=pk, user=request.user)
    except Notification.DoesNotExist:
        return Response(
            {"detail": "Notification introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not notif.lue:
        notif.lue = True
        notif.save(update_fields=["lue", "updated_at"])
    return Response(NotificationReadSerializer(notif).data)


@extend_schema(
    tags=["notifications"],
    summary="Marquer toutes les notifications comme lues",
    responses={200: None},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    updated = Notification.objects.filter(user=request.user, lue=False).update(lue=True)
    return Response({"marked": updated})
