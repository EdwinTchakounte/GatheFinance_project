"""Changement d'image de couverture d'un article → propagation immédiate.

Régression signalée : « quand je change l'image d'un contenu, elle ne
s'affiche pas ». L'admin Next.js s'appuie désormais sur la réponse de l'upload
(`cover_image_data`) pour rafraîchir l'affichage ; on verrouille ici que :

  1. l'endpoint republie bien la page avec la NOUVELLE image,
  2. deux changements successifs renvoient deux URL différentes,
  3. la page rechargée depuis la base reflète la dernière image (source cms).

MEDIA_ROOT est redirigé vers un dossier temporaire (le `media/` du dépôt n'est
pas inscriptible en CI/local).
"""
from __future__ import annotations

import io
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps_cms.cms.models import BlogIndexPage, BlogPostPage, HomePage

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def media_root(tmp_path, settings):
    """Stockage média inscriptible et isolé pour l'upload d'images."""
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (8, 8), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(color, name):
    return SimpleUploadedFile(name, _png_bytes(color), "image/png")


def _blog_post() -> BlogPostPage:
    from wagtail.models import Collection, Locale, Page

    if Collection.get_first_root_node() is None:
        Collection.add_root(name="Root")
    fr, _ = Locale.objects.get_or_create(language_code="fr")
    root = Page.get_first_root_node()

    # Slugs dédiés : une page « home » par défaut existe déjà sous la racine.
    home = HomePage.objects.first()
    if home is None:
        home = HomePage(title="Home CMS test", slug="home-cms-test", locale=fr)
        root.add_child(instance=home)

    blog = BlogIndexPage.objects.first()
    if blog is None:
        blog = BlogIndexPage(title="Blog", slug="blog-cms-test", locale=fr)
        home.add_child(instance=blog)

    post = BlogPostPage(
        title="Article test", slug="article-cms-test", locale=fr,
        date=date(2026, 1, 1),
    )
    blog.add_child(instance=post)
    post.save_revision().publish()
    post.refresh_from_db()
    return post


def _staff_client():
    from django.contrib.auth.models import Group

    u = User.objects.create_user(
        username="cms@t.local", email="cms@t.local", password="pass12345",
        is_staff=True,
    )
    grp, _ = Group.objects.get_or_create(name="staff")
    u.groups.add(grp)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


def _url(pk):
    return f"/api/v1/cms/blog/{pk}/cover-image/"


def test_change_cover_republishes_and_returns_fresh_url(media_root):
    post = _blog_post()
    client = _staff_client()

    r1 = client.post(_url(post.id), {"image": _upload((200, 30, 30), "red.png")})
    assert r1.status_code == 200, r1.content
    data1 = r1.json()["cover_image_data"]
    assert data1 and data1["source"] == "cms"
    url1 = data1["url"]
    assert "/media/" in url1

    # Deuxième changement → NOUVELLE image, NOUVELLE URL.
    r2 = client.post(_url(post.id), {"image": _upload((30, 30, 200), "blue.png")})
    assert r2.status_code == 200, r2.content
    url2 = r2.json()["cover_image_data"]["url"]
    assert url2 != url1, "le changement d'image doit produire une nouvelle URL"

    # La page rechargée depuis la base reflète la dernière image publiée :
    # c'est exactement ce dont dépend l'affichage admin.
    post.refresh_from_db()
    assert post.cover_image_data["url"] == url2
    assert post.cover_image_data["source"] == "cms"


def test_missing_file_is_rejected(media_root):
    post = _blog_post()
    r = _staff_client().post(_url(post.id), {})
    assert r.status_code == 400


def test_non_image_is_rejected(media_root):
    post = _blog_post()
    bad = SimpleUploadedFile("note.txt", b"not an image", "text/plain")
    r = _staff_client().post(_url(post.id), {"image": bad})
    assert r.status_code == 400


def test_requires_staff(media_root):
    post = _blog_post()
    anon = APIClient()
    r = anon.post(_url(post.id), {"image": _upload((10, 10, 10), "x.png")})
    assert r.status_code in (401, 403)
