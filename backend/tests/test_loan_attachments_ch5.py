"""CH-5 — Upload de fichiers attachés à un LoanRequest.

Couvre :
  - POST /api/v1/loans/requests/{id}/attachments/ crée un Document polymorphe
  - Idempotence : re-upload du même schema_field_id remplace le précédent
  - Permission : seul le propriétaire du LoanRequest peut uploader
  - Validation : fichier requis, schema_field_id requis, taille max
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.members.models import Document


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _tmp_media_root(settings, tmp_path):
    """Redirige MEDIA_ROOT vers un dossier temporaire pour éviter les
    permission errors lors de l'écriture sur disque pendant les tests."""
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def loan_request(active_member):
    return LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("100000"),
        duree_mois=6,
        motif="Test CH-5",
        statut=LoanRequest.Statut.EN_ATTENTE,
    )


def _png_file(name="cga.png", size=512):
    return SimpleUploadedFile(name, b"x" * size, content_type="image/png")


class TestUploadAttachment:
    def test_owner_can_upload(self, loan_request, active_member):
        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {
                "fichier": _png_file(),
                "schema_field_id": "cga_attestation",
            },
            format="multipart",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["schema_field_id"] == "cga_attestation"
        assert body["nom_original"].endswith(".png")
        assert body["taille"] == 512

        doc = Document.objects.get(pk=body["id"])
        assert doc.entite_liee_type == "LoanRequest"
        assert doc.entite_liee_id == loan_request.id
        assert doc.member_id == active_member.id

    def test_missing_file_returns_400(self, loan_request, active_member):
        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {"schema_field_id": "cga_attestation"},
            format="multipart",
        )
        assert r.status_code == 400

    def test_missing_schema_field_id_returns_400(self, loan_request, active_member):
        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {"fichier": _png_file()},
            format="multipart",
        )
        assert r.status_code == 400

    def test_other_member_cannot_upload(self, loan_request, suspended_member):
        client = APIClient()
        client.force_authenticate(suspended_member.user)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {
                "fichier": _png_file(),
                "schema_field_id": "cga_attestation",
            },
            format="multipart",
        )
        # suspended_member n'a pas la permission IsActiveMember en premier lieu.
        assert r.status_code in (403, 404)

    def test_anonymous_cannot_upload(self, loan_request):
        client = APIClient()
        r = client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {
                "fichier": _png_file(),
                "schema_field_id": "cga_attestation",
            },
            format="multipart",
        )
        assert r.status_code in (401, 403)

    def test_re_upload_same_field_replaces(self, loan_request, active_member):
        client = APIClient()
        client.force_authenticate(active_member.user)

        # 1er upload
        r1 = client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {
                "fichier": _png_file("cga_v1.png", 100),
                "schema_field_id": "cga_attestation",
            },
            format="multipart",
        )
        assert r1.status_code == 201
        first_id = r1.json()["id"]

        # Re-upload du même schema_field_id
        r2 = client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {
                "fichier": _png_file("cga_v2.png", 200),
                "schema_field_id": "cga_attestation",
            },
            format="multipart",
        )
        assert r2.status_code == 201
        second_id = r2.json()["id"]

        # Le premier a été supprimé, seul le second reste.
        assert not Document.objects.filter(pk=first_id).exists()
        assert Document.objects.filter(pk=second_id).exists()
        assert Document.objects.filter(
            entite_liee_type="LoanRequest",
            entite_liee_id=loan_request.id,
            schema_field_id="cga_attestation",
        ).count() == 1

    def test_different_field_ids_coexist(self, loan_request, active_member):
        client = APIClient()
        client.force_authenticate(active_member.user)
        client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {"fichier": _png_file("cga.png"), "schema_field_id": "cga_attestation"},
            format="multipart",
        )
        client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {"fichier": _png_file("cfp.png"), "schema_field_id": "cfp_attestation"},
            format="multipart",
        )
        assert Document.objects.filter(
            entite_liee_type="LoanRequest",
            entite_liee_id=loan_request.id,
        ).count() == 2

    def test_file_too_large_rejected(self, loan_request, active_member):
        client = APIClient()
        client.force_authenticate(active_member.user)
        big_file = SimpleUploadedFile(
            "big.png", b"x" * (11 * 1024 * 1024), content_type="image/png",
        )
        r = client.post(
            f"/api/v1/loans/requests/{loan_request.id}/attachments/",
            {"fichier": big_file, "schema_field_id": "cga_attestation"},
            format="multipart",
        )
        assert r.status_code == 400
