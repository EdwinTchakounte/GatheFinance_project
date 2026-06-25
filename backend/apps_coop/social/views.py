"""API interactions sociales — likes & commentaires.

Routes membres :
- POST   /social/articles/<id>/like/         toggle like
- GET    /social/articles/<id>/comments/     liste paginee
- POST   /social/articles/<id>/comments/     creer un commentaire
- (idem pour /campaigns/<id>/...)
- DELETE /social/comments/<id>/              supprimer son propre commentaire

Routes staff :
- GET    /social/admin/comments/             liste filtrable
- POST   /social/admin/comments/<id>/hide/   masquer (motif)
- POST   /social/admin/comments/<id>/unhide/ restaurer
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps_coop.common import parse_pagination
from apps_coop.members.permissions import IsStaff

from .models import ContentComment, ContentReaction
from .serializers import (
    AdminCommentSerializer,
    CommentCreateSerializer,
    CommentSerializer,
    HideCommentSerializer,
)
from .services import TARGET_KINDS, get_content_type_for_kind, get_target_or_404


# ---------------------------------------------------------------------------
# Helpers de reponse
# ---------------------------------------------------------------------------


def _reaction_payload(content_type, object_id, user) -> dict:
    """Forme JSON commune pour /like/ — {liked, count}."""
    count = ContentReaction.objects.filter(
        content_type=content_type, object_id=object_id
    ).count()
    liked = (
        user.is_authenticated
        and ContentReaction.objects.filter(
            content_type=content_type, object_id=object_id, user=user
        ).exists()
    )
    return {"liked": liked, "count": count}


# ---------------------------------------------------------------------------
# Like — toggle
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["social"],
    summary="Toggle like sur un contenu",
    description=(
        "Si le membre n'avait pas encore like ce contenu, cree la reaction "
        "et renvoie `liked=True`. Sinon supprime la reaction existante et "
        "renvoie `liked=False`. Le `count` est le total actuel apres toggle."
    ),
    responses={200: OpenApiResponse(description="`{liked: bool, count: int}`")},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def toggle_like(request, kind: str, object_id: int):
    ct, _target = get_target_or_404(kind, object_id)
    existing = ContentReaction.objects.filter(
        content_type=ct, object_id=object_id, user=request.user
    ).first()
    if existing:
        existing.delete()
    else:
        ContentReaction.objects.create(
            content_type=ct, object_id=object_id, user=request.user
        )
    return Response(_reaction_payload(ct, object_id, request.user))


@extend_schema(
    tags=["social"],
    summary="Etat de la reaction du membre + compteur",
    responses={200: OpenApiResponse(description="`{liked: bool, count: int}`")},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_reaction(request, kind: str, object_id: int):
    """Lecture seule — utile pour afficher l'icone coeur initial."""
    ct, _ = get_target_or_404(kind, object_id)
    return Response(_reaction_payload(ct, object_id, request.user))


# ---------------------------------------------------------------------------
# Commentaires — liste / creation par contenu
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["social"],
    summary="Lister / creer les commentaires d'un contenu",
    description=(
        "GET : pagination offset/limit (defaut 20, max 100). Les commentaires "
        "masques sont exclus par defaut pour les membres ; le staff voit "
        "tout avec le flag `hidden` distinct.\n\n"
        "POST : cree un commentaire (body, 1..1000 chars)."
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def comments_for_target(request, kind: str, object_id: int):
    ct, _target = get_target_or_404(kind, object_id)

    if request.method == "GET":
        offset, limit = parse_pagination(request, default_limit=20, max_limit=100)
        qs = ContentComment.objects.filter(
            content_type=ct, object_id=object_id
        ).select_related("user").order_by("-created_at")
        # Membres normaux : on cache les commentaires masques. Le staff voit
        # tout (avec `hidden=True` dans la reponse), c'est utile pour la
        # moderation depuis le mobile en cas de besoin.
        if not request.user.is_staff:
            qs = qs.filter(hidden=False)
        count = qs.count()
        page = list(qs[offset : offset + limit])
        ser = CommentSerializer(page, many=True, context={"request": request})
        return Response(
            {
                "count": count,
                "limit": limit,
                "offset": offset,
                "results": ser.data,
            }
        )

    # POST
    ser = CommentCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    comment = ContentComment.objects.create(
        user=request.user,
        content_type=ct,
        object_id=object_id,
        body=ser.validated_data["body"],
    )
    return Response(
        CommentSerializer(comment, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# Suppression d'un commentaire par son auteur (le staff utilise hide/unhide).
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["social"],
    summary="Supprimer son propre commentaire",
    description=(
        "Un membre peut supprimer son propre commentaire. Le staff doit "
        "preferer `hide/unhide` pour conserver la trace en DB."
    ),
    responses={204: None, 403: None, 404: None},
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_my_comment(request, pk: int):
    try:
        comment = ContentComment.objects.get(pk=pk)
    except ContentComment.DoesNotExist:
        return Response(
            {"detail": "Commentaire introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if comment.user_id != request.user.id:
        return Response(
            {"detail": "Action reservee a l'auteur du commentaire."},
            status=status.HTTP_403_FORBIDDEN,
        )
    comment.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Admin — liste/hide/unhide
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["social"],
    summary="Admin — lister tous les commentaires (filtres + pagination)",
    description=(
        "**Filtres** :\n"
        "- `q` : recherche dans le body et l'email auteur\n"
        "- `hidden` : `1/true` = uniquement masques, `0/false` = uniquement visibles\n"
        "- `content_type` : `article` ou `campaign`\n"
        "- `limit` (defaut 25, max 100), `offset` (defaut 0)"
    ),
    responses={200: OpenApiResponse(description="`{count, results: [...] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_comments_list(request):
    qp = request.query_params
    offset, limit = parse_pagination(request, default_limit=25, max_limit=100)
    qs = ContentComment.objects.select_related(
        "user", "hidden_by", "content_type"
    ).order_by("-created_at")

    q_search = (qp.get("q") or "").strip()
    if q_search:
        qs = qs.filter(
            Q(body__icontains=q_search)
            | Q(user__email__icontains=q_search)
            | Q(user__username__icontains=q_search)
        )

    hidden_raw = (qp.get("hidden") or "").strip().lower()
    if hidden_raw in ("1", "true", "yes"):
        qs = qs.filter(hidden=True)
    elif hidden_raw in ("0", "false", "no"):
        qs = qs.filter(hidden=False)

    content_type_kind = (qp.get("content_type") or "").strip().lower()
    if content_type_kind:
        try:
            ct = get_content_type_for_kind(content_type_kind)
            qs = qs.filter(content_type=ct)
        except Exception:  # noqa: BLE001 — l'erreur 404 du helper n'a pas de sens ici
            return Response(
                {
                    "detail": (
                        f"content_type doit etre l'un de "
                        f"{sorted(TARGET_KINDS)}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    count = qs.count()
    page = list(qs[offset : offset + limit])
    return Response(
        {
            "count": count,
            "limit": limit,
            "offset": offset,
            "results": AdminCommentSerializer(page, many=True).data,
        }
    )


@extend_schema(
    tags=["social"],
    summary="Admin — masquer un commentaire",
    description="Pose `hidden=True` + meta (`hidden_by`, `hidden_at`, `hidden_reason`).",
    request=HideCommentSerializer,
    responses={200: AdminCommentSerializer, 404: None},
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_hide_comment(request, pk: int):
    try:
        comment = ContentComment.objects.get(pk=pk)
    except ContentComment.DoesNotExist:
        return Response(
            {"detail": "Commentaire introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )
    ser = HideCommentSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    comment.hidden = True
    comment.hidden_by = request.user
    comment.hidden_at = timezone.now()
    comment.hidden_reason = ser.validated_data["reason"]
    comment.save(
        update_fields=["hidden", "hidden_by", "hidden_at", "hidden_reason", "updated_at"]
    )
    return Response(AdminCommentSerializer(comment).data)


@extend_schema(
    tags=["social"],
    summary="Admin — restaurer un commentaire masque",
    responses={200: AdminCommentSerializer, 404: None},
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_unhide_comment(request, pk: int):
    try:
        comment = ContentComment.objects.get(pk=pk)
    except ContentComment.DoesNotExist:
        return Response(
            {"detail": "Commentaire introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )
    comment.hidden = False
    comment.hidden_by = None
    comment.hidden_at = None
    comment.hidden_reason = ""
    comment.save(
        update_fields=["hidden", "hidden_by", "hidden_at", "hidden_reason", "updated_at"]
    )
    return Response(AdminCommentSerializer(comment).data)
