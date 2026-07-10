"""Garde-fou : les URL publiques de pages CMS visent la VITRINE, pas le portail.

Régression (404 "Voir" du dashboard) : ``_frontend_url_for`` et
``bootstrap_site`` utilisaient ``FRONTEND_PUBLIC_URL``, qui en prod pointe sur
le PORTAIL membre (``portail.…``). Or les articles ne sont servis que par la
vitrine (``gathe-finance.…``) → ``page.full_url`` = ``portail/blog/<slug>`` →
404. Le hostname du Site Wagtail et les redirections serve()/preview doivent
donc dériver de ``SITE_PUBLIC_URL`` (vitrine).
"""
from __future__ import annotations

from django.test import override_settings
from wagtail.models import Page

import apps_cms.cms.models as cms_models


class _Locale:
    language_code = "fr"


class _FakePage:
    locale = _Locale()


@override_settings(
    SITE_PUBLIC_URL="https://vitrine.example.com",
    FRONTEND_PUBLIC_URL="https://portail.example.com",
    FRONTEND_BASE_URL="https://interne.example.com",
)
def test_frontend_url_uses_site_public_url_not_portal(monkeypatch):
    monkeypatch.setattr(
        Page, "get_url_parts",
        lambda self, request=None: (1, "https://x", "/blog/mon-article/"),
    )
    url = cms_models._frontend_url_for(_FakePage())
    assert url == "https://vitrine.example.com/blog/mon-article", url
    assert "portail" not in url  # jamais le portail membre


@override_settings(
    SITE_PUBLIC_URL="https://vitrine.example.com",
    FRONTEND_PUBLIC_URL="https://portail.example.com",
)
def test_frontend_url_locale_en_prefix(monkeypatch):
    class _En:
        language_code = "en"

    class _EnPage:
        locale = _En()

    monkeypatch.setattr(
        Page, "get_url_parts",
        lambda self, request=None: (1, "https://x", "/blog/my-post/"),
    )
    url = cms_models._frontend_url_for(_EnPage())
    assert url == "https://vitrine.example.com/en/blog/my-post", url
