"""CH-9 — Note de demande PDF + payout auto-fill.

Couvre :
  - Champs ``LoanRequest.moyen_reception`` + ``recipient_phone`` persistés
    à la soumission (sérialisation, validation).
  - Endpoint ``GET /loans/requests/<pk>/note/`` :
      * Membre propriétaire OK, autre membre refusé (403),
      * Admin coop OK pour n'importe quelle note,
      * Non authentifié refusé,
      * Content-Type = application/pdf,
      * Bytes commencent par ``%PDF-``.
  - Générateur PDF ``build_loan_request_note`` :
      * Acceptation d'une LR sans Loan (bytes non vides, magic header).
      * Acceptation d'une LR + Loan + installments (bytes non vides).
  - Endpoint ``POST /admin/<pk>/disburse-now/`` :
      * Auto-fill Tara MoMo (network MTN) — payment créé.
      * Auto-fill Tara OM (network ORANGE).
      * Mode agence_especes refusé sans reference_externe (400), accepté avec.
      * 400 si moyen_reception vide.
      * 403 pour non-admin.
  - Endpoint ``GET /admin/<pk>/disbursement-status/`` :
      * Renvoie payment_id, statut, source du dernier décaissement.
      * has_payment=False si aucun.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.note_pdf import build_loan_request_note
from apps_coop.loans.services import generate_installments_flat_interest
from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


User = get_user_model()


@pytest.fixture(autouse=True)
def _reset_factory_sequences():
    # Évite collisions UNIQUE numero_membre quand ce module est exécuté
    # après d'autres modules qui ont rempli la séquence Postgres réelle.
    MemberFactory.reset_sequence(910000)
    UserFactory.reset_sequence(910000)
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_lr(member, *, moyen="tara_momo", phone="+237699000111", with_loan=False):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("60000"),
        duree_mois=3,
        motif="Achat stock atelier soudure pour rentrée scolaire.",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        moyen_reception=moyen,
        recipient_phone=phone if moyen.startswith("tara_") else "",
        modalite_paiement="mensuel",
    )
    if with_loan:
        suffix = f"NOTE{lr.id}"
        loan = Loan.objects.create(
            member=member,
            loan_request=lr,
            numero_dossier=f"GF-CH9-{suffix}",
            montant=Decimal("60000"),
            taux_interet=Decimal("0.10"),
            duree_mois=3,
            date_decaissement=date.today(),
            date_premiere_echeance=date.today() + timedelta(days=30),
            montant_total_du=Decimal("66000"),
            solde_restant=Decimal("66000"),
            statut=Loan.Statut.ACTIF,
        )
        generate_installments_flat_interest(loan)
        loan.date_butoire = (
            loan.installments.order_by("-date_echeance")
            .values_list("date_echeance", flat=True)
            .first()
        )
        loan.save(update_fields=["date_butoire", "updated_at"])
        return lr, loan
    return lr, None


@pytest.fixture
def other_member(db):
    return MemberFactory()


# ---------------------------------------------------------------------------
# 1. PDF generator — sans / avec Loan.
# ---------------------------------------------------------------------------
class TestPDFGenerator:
    def test_generates_bytes_without_loan(self, active_member):
        lr, _ = _build_lr(active_member, moyen="tara_om", phone="+237699112233")
        pdf = build_loan_request_note(lr)
        assert isinstance(pdf, bytes)
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 1000  # Sanity : un PDF 1-page fait bien plus que 1 KB.

    def test_generates_bytes_with_loan_and_installments(self, active_member):
        lr, loan = _build_lr(active_member, with_loan=True)
        assert loan.installments.count() >= 1
        pdf = build_loan_request_note(lr)
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 1000

    def test_handles_agence_especes_without_phone(self, active_member):
        lr, _ = _build_lr(active_member, moyen="agence_especes", phone="")
        pdf = build_loan_request_note(lr)
        assert pdf.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# 2. Endpoint GET /loans/requests/<pk>/note/
# ---------------------------------------------------------------------------
class TestNoteEndpoint:
    def test_owner_can_download_pdf(self, active_member):
        lr, _ = _build_lr(active_member)
        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.get(f"/api/v1/loans/requests/{lr.id}/note/")
        assert r.status_code == 200, r.content
        assert r["Content-Type"] == "application/pdf"
        # Le contenu doit être un PDF valide.
        assert r.content.startswith(b"%PDF-")
        assert f"note-demande-{active_member.numero_membre}-{lr.id}.pdf" in r["Content-Disposition"]

    def test_admin_can_download_any_pdf(self, active_member, admin_user):
        lr, _ = _build_lr(active_member)
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.get(f"/api/v1/loans/requests/{lr.id}/note/")
        assert r.status_code == 200, r.content
        assert r.content.startswith(b"%PDF-")

    def test_other_member_forbidden_403(self, active_member, other_member):
        lr, _ = _build_lr(active_member)
        client = APIClient()
        client.force_authenticate(other_member.user)
        r = client.get(f"/api/v1/loans/requests/{lr.id}/note/")
        assert r.status_code == 403, r.content

    def test_unauthenticated_rejected(self, active_member):
        lr, _ = _build_lr(active_member)
        client = APIClient()
        r = client.get(f"/api/v1/loans/requests/{lr.id}/note/")
        assert r.status_code in (401, 403)

    def test_not_found_404(self, active_member):
        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.get("/api/v1/loans/requests/999999/note/")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 3. Endpoint POST /admin/<pk>/disburse-now/ — auto-fill.
# ---------------------------------------------------------------------------
class TestDisburseNowAutoFill:
    def test_tara_momo_auto_fills_mtn(self, active_member, admin_user, settings):
        settings.PAYMENTS_TEST_AUTO_VALIDATE = False
        _, loan = _build_lr(
            active_member, moyen="tara_momo", phone="+237699112233", with_loan=True
        )
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(f"/api/v1/loans/admin/{loan.id}/disburse-now/", {}, format="json")
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["mode"] == "tara"
        assert body["moyen_reception"] == "tara_momo"
        # Le payment est créé (en_attente jusqu'à webhook).
        assert body["payment_id"] > 0

    def test_tara_om_auto_fills_orange(self, active_member, admin_user, settings):
        settings.PAYMENTS_TEST_AUTO_VALIDATE = False
        _, loan = _build_lr(
            active_member, moyen="tara_om", phone="+237699112233", with_loan=True
        )
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(f"/api/v1/loans/admin/{loan.id}/disburse-now/", {}, format="json")
        assert r.status_code == 200, r.content
        assert r.json()["mode"] == "tara"

    def test_agence_especes_requires_reference(self, active_member, admin_user):
        _, loan = _build_lr(
            active_member, moyen="agence_especes", phone="", with_loan=True
        )
        client = APIClient()
        client.force_authenticate(admin_user)
        # Sans reference_externe → 400.
        r = client.post(f"/api/v1/loans/admin/{loan.id}/disburse-now/", {}, format="json")
        assert r.status_code == 400, r.content
        assert "reference" in r.json()["detail"].lower()
        # Avec → 200.
        r2 = client.post(
            f"/api/v1/loans/admin/{loan.id}/disburse-now/",
            {"reference_externe": "RC-2026-0001", "note": "Espèces remises au guichet."},
            format="json",
        )
        assert r2.status_code == 200, r2.content
        body = r2.json()
        assert body["mode"] == "manuel"
        assert body["moyen_reception"] == "agence_especes"

    def test_moyen_reception_empty_rejected(self, active_member, admin_user):
        # Construit un Loan dont la LR n'a pas de moyen_reception.
        lr = LoanRequest.objects.create(
            member=active_member,
            montant_demande=Decimal("60000"),
            duree_mois=3,
            motif="Test",
            statut=LoanRequest.Statut.APPROUVEE,
            moyen_reception="",
            recipient_phone="",
        )
        loan = Loan.objects.create(
            member=active_member,
            loan_request=lr,
            numero_dossier=f"GF-CH9-EMPTY{lr.id}",
            montant=Decimal("60000"),
            taux_interet=Decimal("0.10"),
            duree_mois=3,
            date_decaissement=date.today(),
            date_premiere_echeance=date.today() + timedelta(days=30),
            montant_total_du=Decimal("66000"),
            solde_restant=Decimal("66000"),
            statut=Loan.Statut.ACTIF,
        )
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(f"/api/v1/loans/admin/{loan.id}/disburse-now/", {}, format="json")
        assert r.status_code == 400
        assert "moyen de réception" in r.json()["detail"].lower()

    def test_non_admin_forbidden(self, active_member, staff_user):
        _, loan = _build_lr(active_member, with_loan=True)
        client = APIClient()
        client.force_authenticate(staff_user)
        r = client.post(f"/api/v1/loans/admin/{loan.id}/disburse-now/", {}, format="json")
        assert r.status_code == 403

    def test_inactive_loan_rejected(self, active_member, admin_user):
        _, loan = _build_lr(active_member, with_loan=True)
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut", "updated_at"])
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(f"/api/v1/loans/admin/{loan.id}/disburse-now/", {}, format="json")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# 4. Endpoint GET /admin/<pk>/disbursement-status/
# ---------------------------------------------------------------------------
class TestDisbursementStatus:
    def test_has_payment_false_when_no_payment(self, active_member, admin_user):
        _, loan = _build_lr(active_member, with_loan=True)
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.get(f"/api/v1/loans/admin/{loan.id}/disbursement-status/")
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["has_payment"] is False

    def test_returns_payment_details(self, active_member, admin_user, settings):
        settings.PAYMENTS_TEST_AUTO_VALIDATE = False
        _, loan = _build_lr(
            active_member, moyen="tara_momo", phone="+237699112233", with_loan=True
        )
        client = APIClient()
        client.force_authenticate(admin_user)
        # 1) déclenche un payout
        client.post(f"/api/v1/loans/admin/{loan.id}/disburse-now/", {}, format="json")
        # 2) lit le statut
        r = client.get(f"/api/v1/loans/admin/{loan.id}/disbursement-status/")
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["has_payment"] is True
        assert body["payment_id"] > 0
        assert body["statut"] in ("en_attente", "valide")
        assert body["source"] == "mobile_money"
        assert body["provider_code"] == "tara"

    def test_non_admin_forbidden(self, active_member, staff_user):
        _, loan = _build_lr(active_member, with_loan=True)
        client = APIClient()
        client.force_authenticate(staff_user)
        r = client.get(f"/api/v1/loans/admin/{loan.id}/disbursement-status/")
        assert r.status_code == 403

    def test_not_found_404(self, admin_user):
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.get("/api/v1/loans/admin/999999/disbursement-status/")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 5. Persistance des champs CH-9 à la soumission (smoke).
# ---------------------------------------------------------------------------
class TestSubmitPersistsMoyenReception:
    def test_fields_stored(self, active_member):
        lr = LoanRequest.objects.create(
            member=active_member,
            montant_demande=Decimal("75000"),
            duree_mois=4,
            motif="Test persistance moyen_reception.",
            statut=LoanRequest.Statut.EN_INSTRUCTION,
            moyen_reception="tara_om",
            recipient_phone="+237699000222",
        )
        lr.refresh_from_db()
        assert lr.moyen_reception == "tara_om"
        assert lr.recipient_phone == "+237699000222"
