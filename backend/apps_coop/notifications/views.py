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

from .models import Announcement, DeviceToken, Notification
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

    not_expired = Q(expires_at__isnull=True) | Q(expires_at__gt=now)

    # Audience : l'annonce touche le membre si elle est « pour tous », ou pour
    # son statut (actif/suspendu), ou s'il figure dans la sélection nominative.
    audience_q = Q(audience=Announcement.Audience.ALL)
    if member is not None:
        statut = getattr(member, "statut", None)
        if statut == member.Statut.ACTIF:
            audience_q |= Q(audience=Announcement.Audience.ACTIFS)
        elif statut == member.Statut.SUSPENDU:
            audience_q |= Q(audience=Announcement.Audience.SUSPENDUS)
        # Sélection nominative : `audience_member_ids` est un JSONField (liste
        # d'ids). Le lookup `__contains` dessus n'existe QUE sur PostgreSQL —
        # il lève NotSupportedError sur SQLite (dev local + tests). On teste donc
        # l'appartenance en Python : l'ensemble « sélection » est petit et ciblé,
        # le coût est négligeable, et le code marche sur les deux bases.
        selection_ids = [
            a.id
            for a in Announcement.objects.filter(
                not_expired, audience=Announcement.Audience.SELECTION
            ).only("id", "audience_member_ids")
            if member.id in (a.audience_member_ids or [])
        ]
        if selection_ids:
            audience_q |= Q(id__in=selection_ids)

    qs = (
        Announcement.objects.filter(not_expired)
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


# ---------------------------------------------------------------------------
# Push — enregistrement / désenregistrement du jeton d'appareil (FCM/APNs).
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["notifications"],
    summary="Enregistre le jeton push de l'appareil courant",
    description=(
        "Le mobile appelle cet endpoint après login (et à chaque rotation du "
        "jeton FCM). Idempotent : si le jeton existe déjà il est réassocié à "
        "l'utilisateur courant et réactivé."
    ),
    responses={200: None, 400: None},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_device(request):
    token = (request.data.get("token") or "").strip()
    if not token:
        return Response({"detail": "token requis."}, status=status.HTTP_400_BAD_REQUEST)
    platform = (request.data.get("platform") or "android").strip().lower()
    valid = {c[0] for c in DeviceToken.Platform.choices}
    if platform not in valid:
        platform = DeviceToken.Platform.ANDROID
    DeviceToken.objects.update_or_create(
        token=token,
        defaults={
            "user": request.user,
            "platform": platform,
            "active": True,
            "last_seen_at": timezone.now(),
        },
    )
    return Response({"registered": True})


@extend_schema(
    tags=["notifications"],
    summary="Désenregistre un jeton push (logout / désinstall)",
    responses={200: None},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unregister_device(request):
    token = (request.data.get("token") or "").strip()
    if token:
        DeviceToken.objects.filter(user=request.user, token=token).update(active=False)
    return Response({"unregistered": True})


@extend_schema(
    tags=["notifications"],
    summary="Préférences de notification push par catégorie",
    description=(
        "GET renvoie la map { catégorie: bool } (opt-out, défaut tout activé). "
        "POST fusionne une mise à jour partielle : corps `{\"push\": {\"credit\": "
        "false}}` (ou directement `{\"credit\": false}`)."
    ),
    responses={200: None},
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def notification_preferences(request):
    from .preferences import get_push_categories, set_push_categories

    if request.method == "POST":
        payload = request.data or {}
        inner = payload.get("push")
        updates = inner if isinstance(inner, dict) else payload
        result = set_push_categories(request.user, updates or {})
        return Response({"push": result})
    return Response({"push": get_push_categories(request.user)})
