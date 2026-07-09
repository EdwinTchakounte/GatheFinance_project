"""Admin API blog : liste paginée (publiés + brouillons), toggle live,
comptage de commentaires.

L'API Wagtail v2 publique ne renvoie que les pages live → l'admin a besoin d'un
endpoint dédié pour voir/activer/désactiver les articles et prévisualiser le
volume de commentaires.
"""
from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps_cms.cms.models import BlogIndexPage, BlogPostPage, HomePage
from apps_coop.social.models import ContentComment

pytestmark = pytest.mark.django_db

User = get_user_model()


def _staff_client():
    u = User.objects.create_user(
        username="cms@t.local", email="cms@t.local", password="x", is_staff=True
    )
    grp, _ = Group.objects.get_or_create(name="staff")
    u.groups.add(grp)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


def _blog_index():
    from wagtail.models import Locale, Page

    fr, _ = Locale.objects.get_or_create(language_code="fr")
    root = Page.get_first_root_node()
    home = HomePage.objects.first()
    if home is None:
        home = HomePage(title="Home", slug="home-cms-test", locale=fr)
        root.add_child(instance=home)
    blog = BlogIndexPage.objects.first()
    if blog is None:
        blog = BlogIndexPage(title="Blog", slug="blog-cms-test", locale=fr)
        home.add_child(instance=blog)
    return blog, fr


def _post(blog, fr, title, slug, day):
    p = BlogPostPage(title=title, slug=slug, locale=fr, date=date(2026, 1, day))
    blog.add_child(instance=p)
    p.save_revision().publish()
    p.refresh_from_db()
    return p


def test_list_returns_published_and_draft_with_live_flag_and_pagination():
    blog, fr = _blog_index()
    p1 = _post(blog, fr, "Article 1", "a1", 1)
    _post(blog, fr, "Article 2", "a2", 2)
    client = _staff_client()

    r = client.get("/api/v1/cms/blog/?locale=fr")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["count"] == 2
    assert {row["title"] for row in body["results"]} == {"Article 1", "Article 2"}
    assert all(row["live"] is True for row in body["results"])

    # Pagination.
    r1 = client.get("/api/v1/cms/blog/?locale=fr&limit=1&offset=0")
    assert r1.json()["count"] == 2
    assert len(r1.json()["results"]) == 1
    r2 = client.get("/api/v1/cms/blog/?locale=fr&limit=1&offset=1")
    assert len(r2.json()["results"]) == 1
    assert r1.json()["results"][0]["id"] != r2.json()["results"][0]["id"]

    # Désactivation → l'article reste listé mais live=False (invisible en public).
    rd = client.post(f"/api/v1/cms/blog/{p1.id}/live/", {"live": False}, format="json")
    assert rd.status_code == 200, rd.content
    assert rd.json()["live"] is False
    p1.refresh_from_db()
    assert p1.live is False

    listing = {row["id"]: row for row in client.get("/api/v1/cms/blog/?locale=fr").json()["results"]}
    assert listing[p1.id]["live"] is False  # toujours visible côté admin

    # Réactivation.
    ru = client.post(f"/api/v1/cms/blog/{p1.id}/live/", {"live": True}, format="json")
    assert ru.json()["live"] is True


def test_comment_count_is_reported():
    blog, fr = _blog_index()
    p = _post(blog, fr, "Article X", "ax", 3)
    ct = ContentType.objects.get_for_model(BlogPostPage)
    author = User.objects.create_user(username="m@t.local", email="m@t.local", password="x")
    ContentComment.objects.create(content_type=ct, object_id=p.id, user=author, body="Bravo")
    ContentComment.objects.create(content_type=ct, object_id=p.id, user=author, body="Utile")

    r = _staff_client().get("/api/v1/cms/blog/?locale=fr")
    row = next(x for x in r.json()["results"] if x["id"] == p.id)
    assert row["comment_count"] == 2


def test_requires_staff():
    blog, fr = _blog_index()
    _post(blog, fr, "Article", "a", 4)
    assert APIClient().get("/api/v1/cms/blog/").status_code in (401, 403)
