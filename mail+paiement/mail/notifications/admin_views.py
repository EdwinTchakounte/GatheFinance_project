"""Admin endpoints — gestion des annonces broadcast (titre + corps + audience).

Routes (montées sous ``/api/v1/notifications/admin/``) :

  - ``GET    /announcements/``            → liste paginée (50 plus récentes)
  - ``POST   /announcements/``            → création + diffusion immédiate
  - ``DELETE /announcements/<id>/``       → suppression (les notifs déjà reçues
    par les membres sont conservées, on supprime juste la trace côté admin)

Diffusion : la POST crée 1 ``Notification`` in-app par membre cible via
``broadcast_announcement``. Le mobile la voit dans la feature notifications
existante (type = ``annonce``).
"""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import client_ip, record as record_audit
from apps_coop.members.permissions import IsStaff

from .models import Announcement
from .serializers import AnnouncementCreateSerializer, AnnouncementReadSerializer
from .services import broadcast_announcement


@extend_schema(
    tags=["notifications"],
    summary="Liste des annonces broadcast (admin)",
    description=(
        "Renvoie les 50 dernières annonces, du plus récent au plus ancien. "
        "Inclut le nombre de destinataires effectifs (``recipients_count``)."
    ),
    responses={200: AnnouncementReadSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_announcements_list(request):
    qs = Announcement.objects.all()[:50]
    data = AnnouncementReadSerializer(qs, many=True).data
    return Response({"results": data})


@extend_schema(
    tags=["notifications"],
    summary="Créer une annonce et la diffuser immédiatement (admin)",
    description=(
        "POST staff : crée une annonce avec titre + corps + audience, puis "
        "diffuse immédiatement : une ``Notification`` in-app est créée pour "
        "chaque membre cible (filtré selon ``audience``). Le mobile et le "
        "portail des membres concernés voient l'annonce dans leur feed "
        "notifications (type=``annonce``).\n\n"
        "Audiences disponibles :\n"
        "  - ``all`` : tous les membres\n"
        "  - ``actifs`` : seulement statut=actif\n"
        "  - ``suspendus`` : seulement statut=suspendu\n"
        "  - ``selection`` : liste d'ids fournie dans ``audience_member_ids``"
    ),
    request=AnnouncementCreateSerializer,
    responses={201: AnnouncementReadSerializer},
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_announcements_create(request):
    serializer = AnnouncementCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    ann = Announcement.objects.create(
        titre=payload["titre"].strip(),
        corps=payload["corps"].strip(),
        audience=payload["audience"],
        audience_member_ids=payload.get("audience_member_ids") or [],
        lien=(payload.get("lien") or "").strip(),
        image=payload.get("image"),
        expires_at=payload.get("expires_at"),
        author=request.user if request.user.is_authenticated else None,
    )

    created = broadcast_announcement(ann)
    ann.recipients_count = created
    ann.published_at = timezone.now()
    ann.save(update_fields=["recipients_count", "published_at", "updated_at"])

    record_audit(
        user=request.user,
        action="notifications.announcement_broadcast",
        entite_type="Announcement",
        entite_id=ann.pk,
        ip=client_ip(request),
        details={
            "titre": ann.titre,
            "audience": ann.audience,
            "recipients_count": created,
        },
    )

    return Response(
        AnnouncementReadSerializer(ann).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["notifications"],
    summary="Supprimer une annonce (admin)",
    description=(
        "DELETE staff : supprime la trace côté admin. Les ``Notification`` "
        "déjà créées chez les membres restent visibles dans leur feed (on "
        "ne va pas leur retirer un message déjà lu)."
    ),
    responses={204: OpenApiResponse(description="Supprimée.")},
)
@api_view(["DELETE"])
@permission_classes([IsStaff])
def admin_announcements_delete(request, pk: int):
    try:
        ann = Announcement.objects.get(pk=pk)
    except Announcement.DoesNotExist:
        return Response(
            {"detail": "Annonce introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    titre = ann.titre
    ann.delete()

    record_audit(
        user=request.user,
        action="notifications.announcement_deleted",
        entite_type="Announcement",
        entite_id=pk,
        ip=client_ip(request),
        details={"titre": titre},
    )

    return Response(status=status.HTTP_204_NO_CONTENT)
