"""Édition d'un membre actif depuis le dashboard admin (identité + contact +
pièces)."""
from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps_coop.members.models import Document, Member
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _tmp_media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)


def _img(name="p.jpg"):
    return SimpleUploadedFile(name, b"\xff\xd8\xff\xe0", content_type="image/jpeg")


def _admin(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


def test_admin_updates_identity_and_contact(admin_user):
    m = MemberFactory(nom="ANCIEN", prenom="Nom", phone="600")
    c = _admin(admin_user)
    r = c.post(
        f"/api/v1/admin/members/{m.id}/update/",
        {"nom": "NOUVEAU", "prenom": "Prenom", "phone": "699999999"},
        format="multipart",
    )
    assert r.status_code == 200, r.content
    m.refresh_from_db()
    assert m.nom == "NOUVEAU"
    assert m.prenom == "Prenom"
    assert m.phone == "699999999"


def test_admin_updates_email_on_user(admin_user):
    m = MemberFactory()
    c = _admin(admin_user)
    r = c.post(
        f"/api/v1/admin/members/{m.id}/update/",
        {"email": "nouvel@ex.cm"},
        format="multipart",
    )
    assert r.status_code == 200, r.content
    m.user.refresh_from_db()
    assert m.user.email == "nouvel@ex.cm"
    assert m.user.username == "nouvel@ex.cm"


def test_email_clash_is_rejected(admin_user):
    other = MemberFactory()
    other.user.email = "pris@ex.cm"
    other.user.save(update_fields=["email"])
    m = MemberFactory()
    c = _admin(admin_user)
    r = c.post(
        f"/api/v1/admin/members/{m.id}/update/",
        {"email": "pris@ex.cm"},
        format="multipart",
    )
    assert r.status_code == 409


def test_admin_replaces_pieces(admin_user):
    m = MemberFactory()
    c = _admin(admin_user)
    r = c.post(
        f"/api/v1/admin/members/{m.id}/update/",
        {"cni_recto": _img("recto.jpg"), "photo": _img("photo.jpg")},
        format="multipart",
    )
    assert r.status_code == 200, r.content
    docs = Document.objects.filter(member=m)
    assert docs.filter(schema_field_id="cni_recto").exists()
    assert docs.filter(schema_field_id="photo").exists()


def test_update_requires_admin(staff_user):
    m = MemberFactory()
    c = APIClient()
    c.force_authenticate(user=staff_user)  # non-admin
    r = c.post(
        f"/api/v1/admin/members/{m.id}/update/",
        {"nom": "X"},
        format="multipart",
    )
    assert r.status_code == 403
