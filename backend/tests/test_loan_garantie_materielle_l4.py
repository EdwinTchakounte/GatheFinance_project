"""Tests L4 — Voie GARANTIE MATÉRIELLE (fallback sans avaliste).

Règle client : l'évaluation/validation du bien relève du COMITÉ DES PRÊTS
(hors système). Le système se contente de router la demande, tracer la valeur
saisie par l'admin, et laisser le comité décider. Aucun gate de couverture
automatique.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.eligibility_routing import EligibilityRoute, evaluate_routes
from apps_coop.loans.models import Loan, LoanGuarantee, LoanRequest
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount

from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


def _seed_fee():
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais", "montant": Decimal("1000"), "actif": True},
    )


def _new(member):
    member.date_adhesion = date.today() - timedelta(days=30)
    member.save(update_fields=["date_adhesion"])
    return member


def _classic(member, amount):
    ClassicSavingsAccount.objects.update_or_create(
        member=member,
        defaults={"solde": Decimal(amount), "date_ouverture": date.today()},
    )


def _api(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestRoutingGarantieMaterielle:
    def test_flag_matches_when_no_avaliste_no_selfcover(self):
        m = _new(MemberFactory())  # aucune épargne
        res = evaluate_routes(m, montant=Decimal("100000"), garantie_materielle=True)
        assert res.route == EligibilityRoute.GARANTIE_MATERIELLE
        assert res.details["garantie_materielle"] is True

    def test_selfcover_wins_over_material_guarantee(self):
        # Auto-couverture est prioritaire : même avec le flag, si le membre se
        # couvre, on route en direct (pas de garantie matérielle inutile).
        m = _new(MemberFactory())
        _classic(m, Decimal("100000"))
        res = evaluate_routes(m, montant=Decimal("100000"), garantie_materielle=True)
        assert res.route == EligibilityRoute.SENIOR_BRC

    def test_no_flag_skips_voie(self):
        m = _new(MemberFactory())
        res = evaluate_routes(m, montant=Decimal("100000"), garantie_materielle=False)
        assert res.route == EligibilityRoute.NONE

    def test_kill_switch_disables_voie(self):
        from apps_coop.audit.models import AppSetting

        AppSetting.objects.update_or_create(
            cle="loans.eligibility.allow_garantie_materielle",
            defaults={"valeur": "false"},
        )
        m = _new(MemberFactory())
        res = evaluate_routes(m, montant=Decimal("100000"), garantie_materielle=True)
        assert res.route == EligibilityRoute.NONE


# ---------------------------------------------------------------------------
# Soumission via l'API
# ---------------------------------------------------------------------------


class TestSubmitGarantieMaterielle:
    def test_creates_request_flagged_en_attente(self):
        _seed_fee()
        m = _new(MemberFactory())
        r = _api(m).post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "100000",
                "duree_mois": 6,
                "motif": "Achat matériel",
                "garantie_materielle": True,
                "garantie_description": "Terrain titré à Douala",
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["route"] == "garantie_materielle"
        assert body["loan_request"]["statut"] == "en_attente"
        lr = LoanRequest.objects.get(pk=body["loan_request"]["id"])
        assert lr.garantie_materielle is True
        assert "Terrain titré" in lr.garantie_description
        # Pas de gel d'épargne sur cette voie.
        assert lr.montant_gele_demandeur == Decimal("0")


# ---------------------------------------------------------------------------
# Évaluation admin (endpoint dédié, non-bloquant) + approbation
# ---------------------------------------------------------------------------


class TestEvaluateAndApprove:
    def _staff(self):
        u = UserFactory()
        from django.contrib.auth.models import Group

        g, _ = Group.objects.get_or_create(name="staff")
        u.groups.add(g)
        return u

    def _pending_material_request(self):
        borrower = _new(MemberFactory())
        return LoanRequest.objects.create(
            member=borrower,
            montant_demande=Decimal("100000"),
            duree_mois=6,
            motif="Test",
            statut=LoanRequest.Statut.EN_INSTRUCTION,
            garantie_materielle=True,
            garantie_description="Bien X",
        )

    def test_evaluate_endpoint_records_value(self):
        lr = self._pending_material_request()
        staff = self._staff()
        c = APIClient()
        c.force_authenticate(user=staff)
        r = c.post(
            f"/api/v1/loans/requests/{lr.pk}/evaluate-guarantee/",
            {"valeur_estimee": "150000", "note": "Titre vérifié au cadastre"},
            format="json",
        )
        assert r.status_code == 200, r.content
        lr.refresh_from_db()
        assert lr.garantie_valeur_estimee == Decimal("150000")
        assert "Éval commission" in lr.garantie_description

    def test_evaluate_rejects_non_material_request(self):
        borrower = _new(MemberFactory())
        lr = LoanRequest.objects.create(
            member=borrower,
            montant_demande=Decimal("50000"),
            duree_mois=3,
            motif="Test",
            statut=LoanRequest.Statut.EN_INSTRUCTION,
        )
        staff = self._staff()
        c = APIClient()
        c.force_authenticate(user=staff)
        r = c.post(
            f"/api/v1/loans/requests/{lr.pk}/evaluate-guarantee/",
            {"valeur_estimee": "150000"},
            format="json",
        )
        assert r.status_code == 400

    def test_approval_not_blocked_by_value_and_creates_guarantee(self):
        # Le système n'impose PAS valeur ≥ montant : le comité juge. Ici on
        # approuve un dossier dont la valeur (80k) est < montant (100k).
        from apps_coop.loans.services import approve_loan_request

        lr = self._pending_material_request()
        lr.garantie_valeur_estimee = Decimal("80000")
        lr.save(update_fields=["garantie_valeur_estimee"])
        loan = approve_loan_request(
            lr,
            decided_by=self._staff(),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        assert loan.statut == Loan.Statut.ACTIF
        g = LoanGuarantee.objects.get(loan=loan)
        assert g.type_garantie == LoanGuarantee.TypeGarantie.BIEN_IMMOBILIER
        assert g.valeur_estimee == Decimal("80000")
