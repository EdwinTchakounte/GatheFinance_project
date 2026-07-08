"""Tests LOT 18 — Endpoints member-facing mandats d'avaliste.

Couvre :
  GET    /loans/me/avaliste-mandats/
  GET    /loans/me/avaliste-mandats/<id>/
  POST   /loans/me/avaliste-mandats/<id>/respond/

Q13 (non-rétractation) testé : un consent ACCEPTED ne peut pas être refusé.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps_coop.loans.avaliste_services import request_avaliste_consent
from apps_coop.loans.models import AvalisteConsent, LoanRequest
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
from tests.factories import MemberFactory


def _cni_file():
    return SimpleUploadedFile("cni.jpg", b"\xff\xd8\xff", content_type="image/jpeg")


def _accept_body(**extra):
    """L5 — accepter un mandat exige n° CNI + scan CNI de l'avaliste (multipart)."""
    body = {"accept": "true", "cni_avaliste": "CNI-AV-001", "cni_avaliste_fichier": _cni_file()}
    body.update(extra)
    return body


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _tmp_media_root(settings, tmp_path):
    """L5 — l'acceptation upload la CNI de l'avaliste. `media/` est root-owned
    dans cet environnement ; on isole MEDIA_ROOT en tmp pour permettre l'écriture.
    """
    settings.MEDIA_ROOT = str(tmp_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_senior(*, savings_classique=Decimal("0"), savings_collecte=Decimal("0")):
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=400))
    if savings_collecte > 0:
        sa = SavingsAccount.objects.get(member=m)
        sa.solde = savings_collecte
        sa.save(update_fields=["solde"])
    if savings_classique > 0:
        ClassicSavingsAccount.objects.create(
            member=m, solde=savings_classique, date_ouverture=date.today()
        )
    return m


def _make_new(*, savings_collecte=Decimal("0")):
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=30))
    if savings_collecte > 0:
        sa = SavingsAccount.objects.get(member=m)
        sa.solde = savings_collecte
        sa.save(update_fields=["solde"])
    return m


def _pose_consent(*, borrower, senior, montant=Decimal("50000")):
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=montant,
        duree_mois=3,
        motif="Test mandat",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
    )
    return request_avaliste_consent(
        lr, numero_identification=senior.numero_membre, nom=senior.nom
    )


def _client(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


# ---------------------------------------------------------------------------
# GET /loans/me/avaliste-mandats/
# ---------------------------------------------------------------------------


class TestList:
    def test_returns_mandats_where_im_avaliste(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        _pose_consent(borrower=borrower, senior=senior)

        r = _client(senior).get("/api/v1/loans/me/avaliste-mandats/")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["pending"] == 1
        assert body["results"][0]["demandeur"]["numero_membre"] == borrower.numero_membre

    def test_borrower_does_not_see_own_request_as_mandat(self):
        """Le demandeur ne voit pas SON propre mandat avaliste — il n'est pas avaliste."""
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        _pose_consent(borrower=borrower, senior=senior)

        r = _client(borrower).get("/api/v1/loans/me/avaliste-mandats/")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_filter_by_statut(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)
        # Mark as ACCEPTED so we can filter.
        c.statut = AvalisteConsent.Statut.ACCEPTED
        c.save(update_fields=["statut"])

        r = _client(senior).get(
            "/api/v1/loans/me/avaliste-mandats/?statut=accepted"
        )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["pending"] == 0  # plus aucun en pending

        r2 = _client(senior).get(
            "/api/v1/loans/me/avaliste-mandats/?statut=pending"
        )
        assert r2.json()["count"] == 0

    def test_requires_authentication(self):
        c = APIClient()
        r = c.get("/api/v1/loans/me/avaliste-mandats/")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /loans/me/avaliste-mandats/<id>/
# ---------------------------------------------------------------------------


class TestDetail:
    def test_detail_returns_data(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)

        r = _client(senior).get(f"/api/v1/loans/me/avaliste-mandats/{c.id}/")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == c.id
        assert body["loan_request"]["montant_demande"] == "50000.00"
        assert "couverture" in body
        assert "ratio" in body["couverture"]

    def test_detail_404_if_not_my_mandat(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        other = _make_senior()
        c = _pose_consent(borrower=borrower, senior=senior)

        r = _client(other).get(f"/api/v1/loans/me/avaliste-mandats/{c.id}/")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /loans/me/avaliste-mandats/<id>/respond/
# ---------------------------------------------------------------------------


class TestRespond:
    def test_accept_passes_lr_to_en_instruction(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)

        r = _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            _accept_body(),
            format="multipart",
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["statut"] == "accepted"
        assert body["cni_avaliste"] == "CNI-AV-001"
        assert body["cni_avaliste_fichier"]  # url présente
        c.refresh_from_db()
        assert c.loan_request.statut == LoanRequest.Statut.EN_INSTRUCTION
        assert c.loan_request.avaliste_id == senior.id
        assert c.cni_avaliste == "CNI-AV-001"

    def test_refuse_with_motif_marks_lr_rejetee_avaliste(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)

        r = _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            {"accept": False, "motif": "Pas confiance dans le projet."},
            format="json",
        )
        assert r.status_code == 200
        body = r.json()
        assert body["statut"] == "refused"
        assert body["refus_motif"] == "Pas confiance dans le projet."
        c.refresh_from_db()
        assert c.loan_request.statut == LoanRequest.Statut.REJETEE_AVALISTE

    def test_accept_then_refuse_rejected_q13(self):
        """Q13 — non-rétractation : après ACCEPTED, on ne peut plus REFUSED."""
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)

        # Accept
        _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            _accept_body(),
            format="multipart",
        )
        # Refuse → 400
        r = _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            {"accept": False, "motif": "Trop tard"},
            format="json",
        )
        assert r.status_code == 400
        assert "rétractation" in r.json()["detail"].lower()

    def test_double_accept_idempotent(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)

        r1 = _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            _accept_body(),
            format="multipart",
        )
        r2 = _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            _accept_body(),
            format="multipart",
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["statut"] == "accepted"

    def test_respond_404_if_not_my_mandat(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        other = _make_senior()
        c = _pose_consent(borrower=borrower, senior=senior)

        r = _client(other).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            {"accept": True},
            format="json",
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# L5 — CNI de l'avaliste requise à l'acceptation (matérialise l'acte signé)
# ---------------------------------------------------------------------------


class TestL5AvalisteCni:
    def test_accept_without_cni_number_rejected(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)
        r = _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            {"accept": "true", "cni_avaliste_fichier": _cni_file()},
            format="multipart",
        )
        assert r.status_code == 400
        assert "CNI" in r.json()["detail"]
        c.refresh_from_db()
        assert c.statut == AvalisteConsent.Statut.PENDING  # pas accepté

    def test_accept_without_cni_file_rejected(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)
        r = _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            {"accept": "true", "cni_avaliste": "CNI-AV-9"},
            format="multipart",
        )
        assert r.status_code == 400
        c.refresh_from_db()
        assert c.statut == AvalisteConsent.Statut.PENDING

    def test_refuse_needs_no_cni(self):
        borrower = _make_new(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        c = _pose_consent(borrower=borrower, senior=senior)
        r = _client(senior).post(
            f"/api/v1/loans/me/avaliste-mandats/{c.id}/respond/",
            {"accept": False, "motif": "Non"},
            format="json",
        )
        assert r.status_code == 200
        assert r.json()["statut"] == "refused"
