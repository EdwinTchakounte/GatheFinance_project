"""API Support membre.

Membre (fil unique) :
  - GET  /api/v1/support/thread/     → mon fil + messages (marque le staff lu)
  - POST /api/v1/support/messages/   → j'écris un message
  - GET  /api/v1/support/unread/     → compteur non-lus (badge)

Admin/staff (boîte de réception) :
  - GET  /api/v1/support/admin/threads/            → tous les fils
  - GET  /api/v1/support/admin/threads/<pk>/       → messages d'un fil (marque lu)
  - POST /api/v1/support/admin/threads/<pk>/reply/ → je réponds
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.naming import full_name
from apps_coop.members.permissions import IsActiveMember, IsStaff

from . import services
from .models import SupportThread
from .serializers import SupportMessageSerializer, SupportThreadAdminSerializer


# --- Membre -----------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsActiveMember])
def my_thread(request):
    """Mon fil de support. Ouvrir le fil = j'ai lu les réponses du support."""
    member = request.user.member
    thread = services.get_or_create_thread(member)
    services.mark_read(thread, reader="member")
    messages = thread.messages.all()
    return Response(
        {
            "thread_id": thread.id,
            "messages": SupportMessageSerializer(messages, many=True).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsActiveMember])
def post_message(request):
    body = (request.data.get("body") or "").strip()
    if not body:
        return Response(
            {"detail": "Message vide."}, status=status.HTTP_400_BAD_REQUEST
        )
    if len(body) > 4000:
        return Response(
            {"detail": "Message trop long (4000 caractères max)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    msg = services.post_member_message(request.user.member, body)
    return Response(
        SupportMessageSerializer(msg).data, status=status.HTTP_201_CREATED
    )


@api_view(["GET"])
@permission_classes([IsActiveMember])
def my_unread(request):
    thread = SupportThread.objects.filter(member=request.user.member).first()
    return Response({"count": thread.unread_for_member() if thread else 0})


# --- Admin / staff ----------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsStaff])
def admin_threads(request):
    threads = (
        SupportThread.objects.select_related("member")
        .filter(last_message_at__isnull=False)
        .order_by("-last_message_at")
    )
    return Response(SupportThreadAdminSerializer(threads, many=True).data)


@api_view(["GET"])
@permission_classes([IsStaff])
def admin_thread_detail(request, pk: int):
    thread = get_object_or_404(SupportThread.objects.select_related("member"), pk=pk)
    services.mark_read(thread, reader="staff")
    messages = thread.messages.all()
    return Response(
        {
            "thread_id": thread.id,
            "member_numero": thread.member.numero_membre,
            "member_nom": full_name(thread.member.prenom, thread.member.nom),
            "messages": SupportMessageSerializer(messages, many=True).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsStaff])
def admin_reply(request, pk: int):
    thread = get_object_or_404(SupportThread, pk=pk)
    body = (request.data.get("body") or "").strip()
    if not body:
        return Response(
            {"detail": "Réponse vide."}, status=status.HTTP_400_BAD_REQUEST
        )
    msg = services.post_staff_reply(thread, request.user, body)
    return Response(
        SupportMessageSerializer(msg).data, status=status.HTTP_201_CREATED
    )
