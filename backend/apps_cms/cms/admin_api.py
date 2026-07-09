"""Admin API (staff) pour éditer rapidement les articles vitrine.

Permet de changer l'image de couverture d'un article directement depuis
l'espace d'administration Next.js, sans passer par Wagtail : on téléverse un
fichier, il devient l'image Wagtail de couverture, la page est republiée
(ce qui déclenche la revalidation ISR de la vitrine) et on renvoie la nouvelle
`cover_image_data` pour rafraîchir l'affichage immédiatement.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.decorators import (
    api_view,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from wagtail.images.models import Image as WagtailImage

from apps_coop.members.permissions import IsStaff

from .models import BlogPostPage

_MAX_BYTES = 8 * 1024 * 1024  # 8 Mo — garde-fou upload.


@api_view(["POST"])
@permission_classes([IsStaff])
@parser_classes([MultiPartParser, FormParser])
def blog_set_cover_image(request, page_id: int):
    """Remplace l'image de couverture d'un article et republie la page."""
    page = get_object_or_404(BlogPostPage, pk=page_id)

    upload = request.FILES.get("image")
    if not upload:
        return Response({"detail": "Aucun fichier « image » fourni."}, status=400)
    if upload.content_type and not upload.content_type.startswith("image/"):
        return Response({"detail": "Le fichier doit être une image."}, status=400)
    if upload.size and upload.size > _MAX_BYTES:
        return Response({"detail": "Image trop lourde (max 8 Mo)."}, status=400)

    # Dimensions requises par le modèle Image de Wagtail — lues via Willow
    # (dépendance de wagtail.images, toujours disponible).
    try:
        from willow.image import Image as WillowImage

        upload.seek(0)
        width, height = WillowImage.open(upload).get_size()
        upload.seek(0)
    except Exception:  # noqa: BLE001 - fichier corrompu / format non géré
        return Response({"detail": "Image illisible ou format non supporté."}, status=400)

    image = WagtailImage(
        title=(upload.name or page.title)[:255],
        file=upload,
        width=width,
        height=height,
        uploaded_by_user=request.user if request.user.is_authenticated else None,
    )
    image.save()

    page.cover_image = image
    revision = page.save_revision()
    revision.publish()  # → signal page_published → revalidation ISR vitrine.
    page.refresh_from_db()

    return Response({"ok": True, "cover_image_data": page.cover_image_data})


@api_view(["GET"])
@permission_classes([IsStaff])
def blog_list(request):
    """Liste admin des articles — publiés ET dépubliés, paginée, avec le statut
    `live` et le nombre de commentaires.

    L'API Wagtail v2 publique ne renvoie que les pages `live` : impossible d'y
    voir/activer un brouillon. Cet endpoint staff sert la vue complète.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Count

    from apps_coop.social.models import ContentComment

    locale = (request.query_params.get("locale") or "").strip()
    q = (request.query_params.get("q") or "").strip()
    try:
        limit = min(max(int(request.query_params.get("limit", 20)), 1), 100)
    except (TypeError, ValueError):
        limit = 20
    try:
        offset = max(int(request.query_params.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    qs = BlogPostPage.objects.all()
    if locale in ("fr", "en"):
        qs = qs.filter(locale__language_code=locale)
    if q:
        qs = qs.filter(title__icontains=q)
    qs = qs.order_by("-date", "-first_published_at", "-id")

    total = qs.count()
    page_items = list(qs[offset : offset + limit])

    # Comptage des commentaires en une seule requête groupée.
    ct = ContentType.objects.get_for_model(BlogPostPage)
    ids = [p.id for p in page_items]
    counts = {}
    if ids:
        rows = (
            ContentComment.objects.filter(content_type=ct, object_id__in=ids)
            .values("object_id")
            .annotate(n=Count("id"))
        )
        counts = {r["object_id"]: r["n"] for r in rows}

    results = [
        {
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "date": p.date.isoformat() if p.date else None,
            "live": p.live,
            "has_unpublished_changes": p.has_unpublished_changes,
            "html_url": p.full_url,
            "cover_image_data": p.cover_image_data,
            "comment_count": counts.get(p.id, 0),
            "author_name": p.author_name,
        }
        for p in page_items
    ]
    return Response(
        {"count": total, "limit": limit, "offset": offset, "results": results}
    )


@api_view(["POST"])
@permission_classes([IsStaff])
def blog_set_live(request, page_id: int):
    """Active (publie) ou désactive (dépublie) un article. Body: `{live: bool}`.

    Publier/dépublier déclenche `page_published`/`page_unpublished` → la vitrine
    est revalidée (ajout/retrait de l'article) automatiquement.
    """
    page = get_object_or_404(BlogPostPage, pk=page_id)
    want_live = bool(request.data.get("live"))

    if want_live and not page.live:
        page.save_revision().publish()
    elif not want_live and page.live:
        page.unpublish()

    page.refresh_from_db()
    return Response({"id": page.id, "live": page.live})
