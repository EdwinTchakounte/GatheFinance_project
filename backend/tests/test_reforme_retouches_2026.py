"""Retouches réforme 2026 (juillet) — trois correctifs backend.

Couvre :
  #4  Crédit — plus de plancher min 3 mois à la soumission. Une demande de
      2 mois (petit montant) est ACCEPTÉE ; la durée effective reste dérivée du
      montant à l'approbation (paliers Art. 7).
  #6  Cash-in agence — les frais FIXES (carnet, adhésion, inscription) ne
      peuvent pas être validés manuellement avec un montant ≠ tarif officiel.
  #7  Visite terrain — ``LoanRequestReadSerializer`` expose désormais
      ``field_visit_outcome`` / ``field_visit_done_at`` / ``field_visit_note``,
      sans quoi le dashboard ne peut jamais avancer vers la décision définitive.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.payments.models import FeeType, Payment
from apps_coop.savings.models import ClassicSavingsAccount


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers (repris de test_loan_routing_lot15)
# ---------------------------------------------------------------------------


def _seed_study_fee(montant="1000"):
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais de demande de crédit",
                  "montant": Decimal(montant), "actif": True},
    )


def _new_member(member, months_ago=2):
    member.date_adhesion = date.today() - timedelta(days=30 * months_ago)
    member.is_brc_member = False
    member.save(update_fields=["date_adhesion", "is_brc_member"])
    return member


def _seed_classic(member, amount):
    ClassicSavingsAccount.objects.update_or_create(
        member=member,
        defaults={"solde": Decimal(amount), "date_ouverture": date.today()},
    )


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# #4 — Plus de plancher min 3 mois
# ---------------------------------------------------------------------------


class TestNoMinDurationFloor:
    def test_two_month_small_loan_is_accepted(self, active_member):
        """Petit montant (palier = 2 mois) : une demande de 2 mois passe.

        Avant : ``duree_mois`` avait ``min_value=3`` → 400 « minimum 3 mois ».
        """
        _seed_study_fee()
        _new_member(active_member)
        _seed_classic(active_member, 30000)  # auto-couverture (≥ montant)
        r = _api(active_member.user).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "30000", "duree_mois": 2, "motif": "Test 2 mois"},
            format="json",
        )
        assert r.status_code == 201, r.content
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        assert lr.duree_mois == 2

    def test_one_month_is_rejected(self, active_member):
        """Durée réglementaire = [2, 9] mois (Art. 7) : 1 mois est sous le
        plancher et doit être refusé au submit."""
        _seed_study_fee()
        _new_member(active_member)
        _seed_classic(active_member, 30000)
        r = _api(active_member.user).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "30000", "duree_mois": 1, "motif": "Test 1 mois"},
            format="json",
        )
        assert r.status_code == 400, r.content

    def test_ten_months_is_rejected(self, active_member):
        """Plafond réglementaire = 9 mois : 10 dépasse et doit être refusé."""
        _seed_study_fee()
        _new_member(active_member)
        _seed_classic(active_member, 30000)
        r = _api(active_member.user).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "30000", "duree_mois": 10, "motif": "Test 10 mois"},
            format="json",
        )
        assert r.status_code == 400, r.content

    def test_zero_month_still_rejected(self, active_member):
        """Plancher technique : une durée nulle reste invalide."""
        _seed_study_fee()
        _new_member(active_member)
        _seed_classic(active_member, 30000)
        r = _api(active_member.user).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "30000", "duree_mois": 0, "motif": "Test 0"},
            format="json",
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# #6 — Frais fixes : montant verrouillé à la validation manuelle
# ---------------------------------------------------------------------------


class TestFixedFeeCashInAmountLocked:
    URL = "/api/v1/payments/admin/cash-in/"

    def _seed_carnet_fee(self, montant="1000"):
        FeeType.objects.update_or_create(
            code=FeeType.Code.CARNET,
            defaults={"libelle": "Frais de carnet",
                      "montant": Decimal(montant), "actif": True},
        )

    def test_wrong_carnet_amount_rejected(self, active_member, admin_user):
        self._seed_carnet_fee("1000")
        r = _api(admin_user).post(
            self.URL,
            {"member_id": active_member.id, "type": "frais_carnet",
             "montant": 500},
            format="json",
        )
        assert r.status_code == 400, r.content
        assert "fixe" in r.json()["detail"].lower()
        assert not Payment.objects.filter(
            member=active_member, type=Payment.Type.FRAIS_CARNET
        ).exists()

    def test_correct_carnet_amount_accepted(self, active_member, admin_user):
        self._seed_carnet_fee("1000")
        r = _api(admin_user).post(
            self.URL,
            {"member_id": active_member.id, "type": "frais_carnet",
             "montant": 1000},
            format="json",
        )
        assert r.status_code in (200, 201), r.content
        assert Payment.objects.filter(
            member=active_member, type=Payment.Type.FRAIS_CARNET,
            montant=Decimal("1000"),
        ).exists()

    def test_epargne_amount_still_free(self, active_member, admin_user):
        """Un dépôt d'épargne garde un montant LIBRE (pas un frais fixe).

        Montant 1 500 : libre (n'est pas verrouillé sur un tarif catalogue) tout
        en respectant les règles collecte désormais appliquées au cash-in agence
        (multiple de 50 + minimum 1 000/jour). L'ancien 750 servait juste de
        « petit montant arbitraire » — il violait le plancher collecte.
        """
        r = _api(admin_user).post(
            self.URL,
            {"member_id": active_member.id, "type": "epargne", "montant": 1500,
             "nb_jours_couverts": 1},
            format="json",
        )
        assert r.status_code in (200, 201), r.content


# ---------------------------------------------------------------------------
# #7 — Visite terrain exposée par le serializer de lecture
# ---------------------------------------------------------------------------


class TestPaymentReceiptPdf:
    """Reçu de versement PDF — parité portail (#1)."""

    def _make_payment(self, member, **kw):
        from django.utils import timezone

        now = timezone.now()
        defaults = dict(
            member=member,
            montant=Decimal("5000"),
            type=Payment.Type.EPARGNE_CLASSIQUE,
            source=Payment.Source.MANUEL,
            statut=Payment.Statut.VALIDE,
            date_versement=now,
            date_validation=now,
        )
        defaults.update(kw)
        return Payment.objects.create(**defaults)

    def test_owner_downloads_pdf(self, active_member):
        p = self._make_payment(active_member)
        r = _api(active_member.user).get(f"/api/v1/payments/{p.id}/receipt/")
        assert r.status_code == 200, r.content
        assert r["Content-Type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"

    def test_receipt_for_remboursement_type(self, active_member):
        p = self._make_payment(
            active_member, type=Payment.Type.REMBOURSEMENT, montant=Decimal("12000")
        )
        r = _api(active_member.user).get(f"/api/v1/payments/{p.id}/receipt/")
        assert r.status_code == 200, r.content
        assert r.content[:4] == b"%PDF"

    def test_non_owner_gets_404(self, active_member):
        from tests.factories import MemberFactory

        other = MemberFactory()
        p = self._make_payment(other)
        r = _api(active_member.user).get(f"/api/v1/payments/{p.id}/receipt/")
        assert r.status_code == 404


class TestFieldVisitExposedInSerializer:
    def _lr_provisional(self, member):
        return LoanRequest.objects.create(
            member=member,
            montant_demande=Decimal("100000"),
            duree_mois=3,
            motif="Test visite terrain",
            statut=LoanRequest.Statut.APPROUVEE_PROVISOIRE,
        )

    def test_field_visit_post_response_includes_outcome(
        self, active_member, admin_user
    ):
        lr = self._lr_provisional(active_member)
        r = _api(admin_user).post(
            f"/api/v1/loans/requests/{lr.id}/field-visit/",
            {"outcome": "favorable", "note": "Local visité, activité réelle."},
            format="json",
        )
        assert r.status_code == 200, r.content
        body = r.json()
        # C'EST le fix : sans ces clés, l'UI ne voit jamais l'issue de la visite.
        assert body["field_visit_outcome"] == "favorable"
        assert body["field_visit_done_at"] is not None
        assert body["field_visit_note"] == "Local visité, activité réelle."

    def test_admin_list_includes_field_visit_outcome(
        self, active_member, admin_user
    ):
        lr = self._lr_provisional(active_member)
        lr.field_visit_outcome = "favorable"
        lr.save(update_fields=["field_visit_outcome"])
        r = _api(admin_user).get("/api/v1/loans/admin/requests/")
        assert r.status_code == 200, r.content
        row = next(x for x in r.json() if x["id"] == lr.id)
        assert row["field_visit_outcome"] == "favorable"

    def test_member_endpoint_does_not_leak_field_visit_note(self, active_member):
        """SÉCURITÉ : le rapport interne de l'agent (field_visit_note) ne doit
        PAS fuiter vers le membre via « Mes demandes »."""
        lr = self._lr_provisional(active_member)
        lr.field_visit_outcome = "defavorable"
        lr.field_visit_note = "Activité fictive, local inexistant — à rejeter."
        lr.save(update_fields=["field_visit_outcome", "field_visit_note"])

        r = _api(active_member.user).get("/api/v1/loans/me/requests/")
        assert r.status_code == 200, r.content
        row = next(x for x in r.json() if x["id"] == lr.id)
        # Le compte-rendu interne NE doit pas être exposé au membre.
        assert "field_visit_note" not in row
        assert "field_visit_outcome" not in row
