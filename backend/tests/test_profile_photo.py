"""Photo de profil (avatar) — upload par le membre + exposition /auth/me/.

Le membre charge sa photo via ``PATCH /members/me/`` (multipart). Elle est
ensuite renvoyée en URL absolue par ``/members/me/`` ET ``/auth/me/`` pour que
les clients (mobile/portail) affichent l'avatar.
"""
from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (0, 180, 148)).save(buf, format="PNG")
    return buf.getvalue()


def _client(member) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


class TestProfilePhoto:
    def test_patch_uploads_photo_and_returns_url(self, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        m = MemberFactory()
        c = _client(m)
        upload = SimpleUploadedFile("avatar.png", _png_bytes(), content_type="image/png")
        r = c.patch("/api/v1/members/me/", {"photo_profil": upload}, format="multipart")
        assert r.status_code == 200, r.content
        url = r.json().get("photo_profil_url")
        assert url and url.startswith("http"), url
        m.refresh_from_db()
        assert bool(m.photo_profil)

    def test_auth_me_exposes_photo_url(self, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        m = MemberFactory()
        c = _client(m)
        # Avant upload : null.
        assert c.get("/api/v1/auth/me/").json()["member"]["photo_profil_url"] is None
        upload = SimpleUploadedFile("a.png", _png_bytes(), content_type="image/png")
        c.patch("/api/v1/members/me/", {"photo_profil": upload}, format="multipart")
        body = c.get("/api/v1/auth/me/").json()
        assert body["member"]["photo_profil_url"], "photo absente de /auth/me/"

    def test_text_patch_still_works_without_photo(self):
        m = MemberFactory()
        c = _client(m)
        r = c.patch("/api/v1/members/me/", {"prenom": "Nouveau"}, format="json")
        assert r.status_code == 200, r.content
        assert r.json()["prenom"] == "Nouveau"
        assert r.json()["photo_profil_url"] is None
