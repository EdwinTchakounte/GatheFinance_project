"""Justificatif BRC déposé depuis une demande de crédit.

Avant ce lot, une preuve BRC envoyée sur le formulaire de demande de crédit
n'existait que comme pièce jointe du ``LoanRequest`` : la file de validation
``/brc`` du back-office restait vide et l'admin ne pouvait jamais poser
``Member.is_brc_member``. On verrouille ici le chemin corrigé.

Couvre :
  - upload sur ``cga_brc_preuve`` / ``cfp_brc_preuve`` → ``BRCDocument`` créé
    en attente, tracé vers la demande d'origine ;
  - un champ non-BRC ne crée rien ;
  - re-upload = remplacement (pas de doublon dans la file) ;
  - la file admin ``/admin/brc/`` expose bien la ligne et sa provenance.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.members.models import BRCDocument

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _tmp_media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def loan_request(active_member):
    return LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("100000"),
        duree_mois=6,
        motif="Test BRC",
        statut=LoanRequest.Statut.EN_ATTENTE,
    )


def _file(name="brc.png", size=256):
    return SimpleUploadedFile(name, b"x" * size, content_type="image/png")


def _upload(client, loan_request, field_id, name="brc.png"):
    return client.post(
        f"/api/v1/loans/requests/{loan_request.id}/attachments/",
        {"fichier": _file(name), "schema_field_id": field_id},
        format="multipart",
    )


@pytest.mark.parametrize("field_id", ["cga_brc_preuve", "cfp_brc_preuve"])
def test_preuve_brc_alimente_la_file_de_validation(
    loan_request, active_member, field_id
):
    client = APIClient()
    client.force_authenticate(active_member.user)

    r = _upload(client, loan_request, field_id)
    assert r.status_code == 201, r.content
    assert r.json()["brc_document_id"] is not None

    doc = BRCDocument.objects.get(member=active_member)
    assert doc.statut == BRCDocument.Statut.EN_ATTENTE
    assert doc.loan_request_id == loan_request.id
    assert doc.champ_source == field_id
    assert doc.taille == 256


def test_champ_non_brc_ne_cree_rien(loan_request, active_member):
    client = APIClient()
    client.force_authenticate(active_member.user)

    r = _upload(client, loan_request, "titre_propriete")
    assert r.status_code == 201, r.content
    assert r.json()["brc_document_id"] is None
    assert not BRCDocument.objects.filter(member=active_member).exists()


def test_reupload_remplace_sans_doublon(loan_request, active_member):
    client = APIClient()
    client.force_authenticate(active_member.user)

    _upload(client, loan_request, "cga_brc_preuve", name="v1.png")
    _upload(client, loan_request, "cga_brc_preuve", name="v2.png")

    docs = BRCDocument.objects.filter(member=active_member)
    assert docs.count() == 1
    assert docs.first().nom_original == "v2.png"


def test_file_admin_expose_la_provenance(loan_request, active_member, admin_user):
    member_client = APIClient()
    member_client.force_authenticate(active_member.user)
    _upload(member_client, loan_request, "cga_brc_preuve")

    staff = APIClient()
    staff.force_authenticate(admin_user)
    r = staff.get("/api/v1/admin/brc/?statut=en_attente")
    assert r.status_code == 200, r.content

    rows = r.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["loan_request_id"] == loan_request.id
    assert row["champ_source"] == "cga_brc_preuve"
    assert "Broad Range" in row["champ_source_display"]
    assert row["fichier_url"].startswith("/media/")
