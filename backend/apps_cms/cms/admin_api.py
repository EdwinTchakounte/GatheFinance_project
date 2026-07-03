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
