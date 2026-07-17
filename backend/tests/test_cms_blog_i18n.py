"""Admin API blog — correspondance anglaise (i18n vitrine).

Édition des champs EN (titre / extrait / contenu) depuis le dashboard, sans
passer par Wagtail. Champs optionnels (vide = pas de traduction → la vitrine
retombe sur le FR).
"""
from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_cms.cms.models import BlogIndexPage, BlogPostPage, HomePage

pytestmark = pytest.mark.django_db

User = get_user_model()


def _staff_client():
    u = User.objects.create_user(
        username="cmsi18n@t.local", email="cmsi18n@t.local", password="x",
        is_staff=True,
    )
    grp, _ = Group.objects.get_or_create(name="staff")
    u.groups.add(grp)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


def _ensure_root(fr):
    from django.contrib.contenttypes.models import ContentType
    from wagtail.models import Page

    root = Page.get_first_root_node()
    if root is None:
        root = Page.add_root(
            title="Root",
            slug="root",
            content_type=ContentType.objects.get_for_model(Page),
            locale=fr,
        )
    return root


def _blog_index():
    from wagtail.models import Locale

    fr, _ = Locale.objects.get_or_create(language_code="fr")
    root = _ensure_root(fr)
    home = HomePage.objects.first()
    if home is None:
        home = HomePage(title="Home", slug="home-i18n-test", locale=fr)
        root.add_child(instance=home)
    blog = BlogIndexPage.objects.first()
    if blog is None:
        blog = BlogIndexPage(title="Blog", slug="blog-i18n-test", locale=fr)
        home.add_child(instance=blog)
    return blog, fr


def _post(title="Épargne", slug="epargne-i18n"):
    blog, fr = _blog_index()
    p = BlogPostPage(
        title=title, slug=slug, locale=fr, date=date(2026, 1, 10),
        excerpt="Extrait FR",
    )
    blog.add_child(instance=p)
    p.save_revision().publish()
    p.refresh_from_db()
    return p


class TestBlogI18nEndpoint:
    def test_get_renvoie_les_champs_en_vides_par_defaut(self):
        p = _post()
        c = _staff_client()
        r = c.get(f"/api/v1/cms/blog/{p.id}/i18n/")
        assert r.status_code == 200
        assert r.data["title"] == "Épargne"
        assert r.data["excerpt"] == "Extrait FR"
        assert r.data["title_en"] == ""
        assert r.data["excerpt_en"] == ""
        assert r.data["body_en"] == ""

    def test_post_enregistre_la_correspondance_en(self):
        p = _post()
        c = _staff_client()
        r = c.post(
            f"/api/v1/cms/blog/{p.id}/i18n/",
            {
                "title_en": "Savings",
                "excerpt_en": "EN excerpt",
                "body_en": "<p>English body</p>",
            },
            format="json",
        )
        assert r.status_code == 200
        assert r.data["title_en"] == "Savings"
        p.refresh_from_db()
        assert p.title_en == "Savings"
        assert p.excerpt_en == "EN excerpt"
        assert "English body" in str(p.body_en)

    def test_post_vide_efface_la_traduction(self):
        p = _post()
        p.title_en = "Savings"
        p.save()
        c = _staff_client()
        r = c.post(
            f"/api/v1/cms/blog/{p.id}/i18n/",
            {"title_en": "", "excerpt_en": "", "body_en": ""},
            format="json",
        )
        assert r.status_code == 200
        p.refresh_from_db()
        assert p.title_en == ""

    def test_blog_list_expose_has_en(self):
        p = _post()
        p.title_en = "Savings"
        p.save()
        c = _staff_client()
        r = c.get("/api/v1/cms/blog/")
        assert r.status_code == 200
        row = next((x for x in r.data["results"] if x["id"] == p.id), None)
        assert row is not None
        assert row["has_en"] is True

    def test_non_staff_refuse(self):
        p = _post()
        u = User.objects.create_user(
            username="member-i18n@t.local", email="member-i18n@t.local",
            password="x",
        )
        c = APIClient()
        c.force_authenticate(user=u)
        r = c.get(f"/api/v1/cms/blog/{p.id}/i18n/")
        assert r.status_code in (401, 403)
