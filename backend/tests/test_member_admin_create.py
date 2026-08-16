"""M1 — Ajout d'un membre depuis le dashboard admin + pièces à la définition
du mot de passe (cas particulier : les pièces n'ont pas transité par le
formulaire public d'adhésion)."""
from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps_coop.members.models import Document, Member, PasswordSetupToken

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _tmp_media_root(settings, tmp_path):
    """`media/` est root-owned dans cet environnement ; on isole MEDIA_ROOT en
    tmp pour permettre l'écriture des pièces uploadées."""
    settings.MEDIA_ROOT = str(tmp_path)


CREATE_URL = "/api/v1/admin/members/create/"
VERIFY_URL = "/api/v1/auth/setup-password/verify/"
CONFIRM_URL = "/api/v1/auth/setup-password/confirm/"


def _img(name="p.jpg"):
    return SimpleUploadedFile(name, b"\xff\xd8\xff\xe0", content_type="image/jpeg")


def _admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


def test_admin_create_member(admin_user, django_capture_on_commit_callbacks):
    c = _admin_client(admin_user)
    # Le mail de bienvenue (qui émet le token) est différé à on_commit.
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post(CREATE_URL, {"nom": "MBALLA", "prenom": "Sophie",
                   "email": "sophie@ex.cm", "phone": "699"}, format="json")
    assert r.status_code == 201, r.content
    m = Member.objects.get(pk=r.json()["id"])
    assert m.statut == Member.Statut.SUSPENDU
    assert m.pieces_a_fournir is True
    # Token de setup émis (mail de bienvenue on_commit).
    assert PasswordSetupToken.objects.filter(user=m.user).exists()


def test_admin_created_member_has_adhesion_sheet(admin_user):
    """Ajout manuel → la fiche d'adhésion doit être disponible (plus de 404)."""
    c = _admin_client(admin_user)
    r = c.post(
        CREATE_URL,
        {"nom": "NGONO", "prenom": "Paul", "email": "paul@ex.cm", "phone": "677"},
        format="json",
    )
    assert r.status_code == 201, r.content
    mid = r.json()["id"]
    res = c.get(f"/api/v1/admin/members/{mid}/adhesion/")
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["identity"]["nom"] == "NGONO"
    assert body["identity"]["prenom"] == "Paul"
    assert body["identity"]["email"] == "paul@ex.cm"
    assert body["statut"] == "approuvee"


def test_adhesion_fallback_for_member_without_request(admin_user):
    """Membre SANS demande liée (legacy / créé avant le fix) → la fiche
    d'adhésion tombe sur les données du membre (200, plus de 404)."""
    from tests.factories import MemberFactory

    c = _admin_client(admin_user)
    m = MemberFactory(nom="LEGACY", prenom="Jean")  # pas de MembershipRequest
    res = c.get(f"/api/v1/admin/members/{m.id}/adhesion/")
    assert res.status_code == 200, res.content
    assert res.json()["identity"]["nom"] == "LEGACY"
    assert res.json()["source"] == "membre"


def test_admin_create_requires_admin(staff_user):
    c = APIClient()
    c.force_authenticate(user=staff_user)  # non-admin
    r = c.post(CREATE_URL, {"nom": "X", "email": "x@ex.cm"}, format="json")
    assert r.status_code == 403


def test_admin_create_duplicate_email_conflicts(admin_user):
    c = _admin_client(admin_user)
    c.post(CREATE_URL, {"nom": "A", "email": "dup@ex.cm"}, format="json")
    r = c.post(CREATE_URL, {"nom": "B", "email": "dup@ex.cm"}, format="json")
    assert r.status_code == 409


def test_setup_flow_requires_and_stores_pieces(admin_user):
    from apps_coop.members.services import issue_password_setup_token

    c = _admin_client(admin_user)
    r = c.post(CREATE_URL, {"nom": "MBALLA", "prenom": "Sophie",
               "email": "sophie2@ex.cm"}, format="json")
    m = Member.objects.get(pk=r.json()["id"])
    assert m.pieces_a_fournir is True
    # Token émis directement (découple ce test du mail on_commit).
    tok = issue_password_setup_token(user=m.user).token

    anon = APIClient()
    # verify signale pieces_required
    rv = anon.get(VERIFY_URL, {"token": tok})
    assert rv.status_code == 200 and rv.json()["pieces_required"] is True

    # confirm sans pièces → 400
    r400 = anon.post(CONFIRM_URL, {"token": tok, "password": "MotDePasse123"}, format="multipart")
    assert r400.status_code == 400
    assert "manquantes" in r400.json()["detail"].lower()

    # confirm avec pièces → 200 + Documents + flag retiré
    r200 = anon.post(CONFIRM_URL, {
        "token": tok, "password": "MotDePasse123",
        "cni": _img("cni.jpg"), "photo": _img("photo.jpg"), "plan": _img("plan.jpg"),
    }, format="multipart")
    assert r200.status_code == 200, r200.content
    m.refresh_from_db()
    assert m.pieces_a_fournir is False
    docs = Document.objects.filter(member=m)
    assert docs.count() == 3
    assert docs.filter(type_doc=Document.TypeDoc.PIECE_IDENTITE, schema_field_id="cni").exists()
    assert m.user.check_password("MotDePasse123")


def test_normal_setup_member_needs_no_pieces(admin_user):
    """Un membre sans pieces_a_fournir (parcours adhésion normal) n'a PAS à
    charger de pièces : confirm avec juste le mot de passe suffit."""
    from apps_coop.members.services import issue_password_setup_token
    from tests.factories import MemberFactory

    m = MemberFactory()  # pieces_a_fournir défaut False
    tok = issue_password_setup_token(user=m.user).token
    anon = APIClient()
    rv = anon.get(VERIFY_URL, {"token": tok})
    assert rv.json()["pieces_required"] is False
    r = anon.post(CONFIRM_URL, {"token": tok, "password": "MotDePasse123"}, format="multipart")
    assert r.status_code == 200, r.content
