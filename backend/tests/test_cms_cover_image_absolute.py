"""L'URL d'image de couverture (`cover_image_data`) doit être ABSOLUE.

Régression : l'admin Next.js / le mobile / le portail consomment cette URL
depuis un autre hôte que l'API. Un chemin relatif `/media/…` s'y résout contre
le mauvais domaine → image cassée après upload. On garantit ici que l'URL sort
toujours absolue (préfixée par le host public du backend).
"""
from __future__ import annotations

import io

import pytest
from django.test import override_settings

from apps_cms.cms.models import BlogPostPage, _absolute_media_url


def _png_bytes() -> bytes:
    """Un PNG 4×4 minimal via Pillow (dispo car Wagtail images en dépend)."""
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (4, 4), (10, 120, 90)).save(buf, format="PNG")
    return buf.getvalue()


# --- Helper pur : pas de DB -------------------------------------------------

@override_settings(WAGTAILADMIN_BASE_URL="https://cms.example.com")
def test_absolute_media_url_prefixes_relative():
    assert _absolute_media_url("/media/images/x.jpg") == "https://cms.example.com/media/images/x.jpg"


@override_settings(WAGTAILADMIN_BASE_URL="https://cms.example.com")
def test_absolute_media_url_leaves_absolute_untouched():
    assert _absolute_media_url("https://cdn.example.com/x.jpg") == "https://cdn.example.com/x.jpg"
    assert _absolute_media_url("//cdn.example.com/x.jpg") == "//cdn.example.com/x.jpg"


def test_absolute_media_url_none_passthrough():
    assert _absolute_media_url(None) is None
    assert _absolute_media_url("") == ""


# --- Intégration : rendition réelle ----------------------------------------

@pytest.mark.django_db
@override_settings(WAGTAILADMIN_BASE_URL="https://cms.example.com")
def test_cover_image_data_url_is_absolute_with_upload(tmp_path, settings):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from wagtail.images.models import Image as WagtailImage
    from wagtail.models import Collection

    # Le `media/` du dépôt n'est pas inscriptible en CI/local → dossier temp.
    settings.MEDIA_ROOT = str(tmp_path)

    if Collection.get_first_root_node() is None:
        Collection.add_root(name="Root")

    img = WagtailImage(title="cover", width=4, height=4)
    img.file.save("cover.png", SimpleUploadedFile("cover.png", _png_bytes(), "image/png"))
    img.save()

    page = BlogPostPage(title="Article test", cover_image=img)
    data = page.cover_image_data

    assert data["source"] == "cms"
    assert data["url"].startswith("http"), data["url"]
    assert "/media/" in data["url"] or data["url"].startswith("https://cms.example.com")


@pytest.mark.django_db
def test_cover_image_data_stock_fallback_is_absolute():
    """Sans image éditeur → photo stock, déjà absolue (Unsplash)."""
    page = BlogPostPage(title="Crédit PME et développement")
    data = page.cover_image_data
    assert data["source"] == "stock"
    assert data["url"].startswith("http"), data["url"]
