"""CH-6 — Double approbation crédit (provisoire → visite terrain → définitive).

Couvre le workflow nouveau :
  EN_INSTRUCTION → APPROUVEE_PROVISOIRE → (visite favorable) → APPROUVEE
  EN_INSTRUCTION → APPROUVEE_PROVISOIRE → (visite défavorable) → REJETEE

Endpoints testés :
  POST /loans/requests/{id}/decide-provisional/
  POST /loans/requests/{id}/field-visit/
  POST /loans/requests/{id}/decide/  (réutilisé pour la décision définitive)
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest


pytestmark = pytest.mark.django_db


User = get_user_model()


@pytest.fixture
def comite_user(db):
    u = User.objects.create_user(
        email="comite@gathe.test", password="x", username="comite",
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u


@pytest.fixture
def staff_user_ch6(db):
    u = User.objects.create_user(
        email="staff@gathe.test", password="x", username="staffch6",
    )
    g, _ = Group.objects.get_or_create(name="staff")
    u.groups.add(g)
    return u


@pytest.fixture
def loan_request_en_instruction(active_member):
    return LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("100000"),
        duree_mois=6,
        motif="Test CH-6",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
    )


class TestDecideProvisional:
    def test_comite_can_approve_provisionally(self, loan_request_en_instruction, comite_user):
        client = APIClient()
        client.force_authenticate(comite_user)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request_en_instruction.id}/decide-provisional/",
            {"avis_provisoire": "Dossier solide, sous réserve visite terrain."},
            format="json",
        )
        assert r.status_code == 200, r.content
        loan_request_en_instruction.refresh_from_db()
        assert loan_request_en_instruction.statut == LoanRequest.Statut.APPROUVEE_PROVISOIRE
        assert loan_request_en_instruction.decide_par_id == comite_user.id
        assert "[Provisoire]" in loan_request_en_instruction.avis_instruction

    def test_avis_required(self, loan_request_en_instruction, comite_user):
        client = APIClient()
        client.force_authenticate(comite_user)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request_en_instruction.id}/decide-provisional/",
            {"avis_provisoire": ""},
            format="json",
        )
        assert r.status_code == 400

    def test_staff_without_comite_cannot(self, loan_request_en_instruction, staff_user_ch6):
        client = APIClient()
        client.force_authenticate(staff_user_ch6)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request_en_instruction.id}/decide-provisional/",
            {"avis_provisoire": "OK"},
            format="json",
        )
        assert r.status_code == 403

    def test_cannot_from_wrong_status(self, loan_request_en_instruction, comite_user):
        loan_request_en_instruction.statut = LoanRequest.Statut.EN_ATTENTE
        loan_request_en_instruction.save(update_fields=["statut", "updated_at"])
        client = APIClient()
        client.force_authenticate(comite_user)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request_en_instruction.id}/decide-provisional/",
            {"avis_provisoire": "OK"},
            format="json",
        )
        assert r.status_code == 400


class TestFieldVisit:
    @pytest.fixture
    def lr_provisional(self, loan_request_en_instruction):
        loan_request_en_instruction.statut = LoanRequest.Statut.APPROUVEE_PROVISOIRE
        loan_request_en_instruction.save(update_fields=["statut", "updated_at"])
        return loan_request_en_instruction

    def test_staff_can_record_favorable_visit(self, lr_provisional, staff_user_ch6):
        client = APIClient()
        client.force_authenticate(staff_user_ch6)
        r = client.post(
            f"/api/v1/loans/requests/{lr_provisional.id}/field-visit/",
            {"outcome": "favorable", "note": "Activité réelle, local visité, RAS."},
            format="json",
        )
        assert r.status_code == 200, r.content
        lr_provisional.refresh_from_db()
        assert lr_provisional.field_visit_outcome == "favorable"
        assert lr_provisional.field_visit_by_id == staff_user_ch6.id
        assert lr_provisional.field_visit_done_at is not None
        # Statut inchangé : on attend la décision définitive du comité.
        assert lr_provisional.statut == LoanRequest.Statut.APPROUVEE_PROVISOIRE

    def test_invalid_outcome_rejected(self, lr_provisional, staff_user_ch6):
        client = APIClient()
        client.force_authenticate(staff_user_ch6)
        r = client.post(
            f"/api/v1/loans/requests/{lr_provisional.id}/field-visit/",
            {"outcome": "random", "note": "x"},
            format="json",
        )
        assert r.status_code == 400

    def test_note_required(self, lr_provisional, staff_user_ch6):
        client = APIClient()
        client.force_authenticate(staff_user_ch6)
        r = client.post(
            f"/api/v1/loans/requests/{lr_provisional.id}/field-visit/",
            {"outcome": "favorable", "note": ""},
            format="json",
        )
        assert r.status_code == 400

    def test_cannot_visit_if_not_provisional(self, loan_request_en_instruction, staff_user_ch6):
        client = APIClient()
        client.force_authenticate(staff_user_ch6)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request_en_instruction.id}/field-visit/",
            {"outcome": "favorable", "note": "test"},
            format="json",
        )
        assert r.status_code == 400


class TestDecideFromProvisional:
    """La décision définitive (approve/reject) accepte aussi APPROUVEE_PROVISOIRE."""

    def test_reject_from_provisional_succeeds(self, loan_request_en_instruction, comite_user):
        loan_request_en_instruction.statut = LoanRequest.Statut.APPROUVEE_PROVISOIRE
        loan_request_en_instruction.field_visit_outcome = "defavorable"
        loan_request_en_instruction.save(update_fields=[
            "statut", "field_visit_outcome", "updated_at",
        ])
        client = APIClient()
        client.force_authenticate(comite_user)
        r = client.post(
            f"/api/v1/loans/requests/{loan_request_en_instruction.id}/decide/",
            {"decision": "rejetee", "motif_rejet": "Visite défavorable."},
            format="json",
        )
        assert r.status_code == 200, r.content
        loan_request_en_instruction.refresh_from_db()
        assert loan_request_en_instruction.statut == LoanRequest.Statut.REJETEE
