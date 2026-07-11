"""Tests LOT 19 — Endpoints member-facing pour la convention prêteur.

Couvre :
  GET    /savings/me/lender/
  POST   /savings/me/lender/opt-in/
  POST   /savings/me/lender/revoke/
  POST   /savings/me/lender/tranches/
  POST   /savings/me/lender/tranches/<id>/cancel/
  POST   /savings/me/lender/funding-requests/<id>/respond/
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.loans.funding_services import request_funding
from apps_coop.loans.models import (
    LenderConsentRequest,
    LoanRequest,
)
from apps_coop.loans.models import Loan
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    LenderConsent,
    LenderTranche,
)
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def _set_min_tranche(amount="1000"):
    AppSetting.objects.update_or_create(
        cle="lender.tranche.min_amount", defaults={"valeur": amount}
    )


def _build_loan(borrower, *, montant=Decimal("50000"), suffix="X"):
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=montant,
        duree_mois=3,
        motif="Test funding LOT 19",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=borrower,
        loan_request=lr,
        numero_dossier=f"GF-LOT19-{suffix}",
        montant=montant,
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=montant * Decimal("1.10"),
        solde_restant=montant * Decimal("1.10"),
        statut=Loan.Statut.ACTIF,
    )


def _make_active_lender(*, mode_global=True, classic_solde=Decimal("200000")):
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=400))
    if classic_solde > 0:
        ClassicSavingsAccount.objects.create(
            member=m, solde=classic_solde, date_ouverture=date.today()
        )
    opt_in_lender(member=m, is_global=mode_global)
    return m


# ---------------------------------------------------------------------------
# GET /savings/me/lender/
# ---------------------------------------------------------------------------


class TestState:
    def test_returns_empty_state_when_not_lender(self, active_member):
        r = _client(active_member).get("/api/v1/savings/me/lender/")
        assert r.status_code == 200
        body = r.json()
        assert body["consent"] is None
        assert body["tranches"] == []
        assert body["pending_count"] == 0

    def test_returns_consent_and_tranches(self, active_member):
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])
        _set_min_tranche("1000")
        opt_in_lender(member=active_member, is_global=False)
        add_tranche(member=active_member, montant=Decimal("10000"))
        add_tranche(member=active_member, montant=Decimal("20000"))

        r = _client(active_member).get("/api/v1/savings/me/lender/")
        assert r.status_code == 200
        body = r.json()
        assert body["consent"]["is_active"] is True
        assert body["consent"]["is_global"] is False
        assert len(body["tranches"]) == 2
        assert body["totals"]["disponible"] == "30000.00"


# ---------------------------------------------------------------------------
# POST /savings/me/lender/opt-in/
# ---------------------------------------------------------------------------


class TestOptIn:
    def test_signs_convention_mode_b(self, active_member):
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])
        r = _client(active_member).post(
            "/api/v1/savings/me/lender/opt-in/",
            {"is_global": False},
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["consent"]["is_active"] is True
        assert body["consent"]["is_global"] is False
        assert LenderConsent.objects.filter(member=active_member).exists()

    def test_opt_in_idempotent_returns_200(self, active_member):
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])
        opt_in_lender(member=active_member, is_global=False)
        r = _client(active_member).post(
            "/api/v1/savings/me/lender/opt-in/",
            {"is_global": True},
            format="json",
        )
        assert r.status_code == 200
        # Mode bascule vers global.
        assert r.json()["consent"]["is_global"] is True

    def test_seniority_block(self, active_member):
        """Avec lender.consent.min_seniority_months posé, un membre récent est bloqué."""
        AppSetting.objects.update_or_create(
            cle="lender.consent.min_seniority_months",
            defaults={"valeur": "24"},
        )
        active_member.date_adhesion = date.today() - timedelta(days=30)
        active_member.save(update_fields=["date_adhesion"])
        r = _client(active_member).post(
            "/api/v1/savings/me/lender/opt-in/",
            {"is_global": False},
            format="json",
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /savings/me/lender/revoke/
# ---------------------------------------------------------------------------


class TestRevoke:
    def test_revokes_clean(self, active_member):
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])
        opt_in_lender(member=active_member, is_global=True)
        r = _client(active_member).post(
            "/api/v1/savings/me/lender/revoke/", {}, format="json"
        )
        assert r.status_code == 200
        assert r.json()["consent"]["is_active"] is False

    def test_revoke_404_if_no_consent(self, active_member):
        r = _client(active_member).post(
            "/api/v1/savings/me/lender/revoke/", {}, format="json"
        )
        assert r.status_code == 404

    def test_revoke_blocked_if_tranche_engagee(self, active_member):
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])
        _set_min_tranche("1000")
        opt_in_lender(member=active_member, is_global=False)
        t = add_tranche(member=active_member, montant=Decimal("10000"))
        t.statut = LenderTranche.Statut.ENGAGEE
        t.save(update_fields=["statut"])

        r = _client(active_member).post(
            "/api/v1/savings/me/lender/revoke/", {}, format="json"
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /savings/me/lender/tranches/
# ---------------------------------------------------------------------------


class TestAddTranche:
    def test_creates_disponible(self, active_member):
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])
        _set_min_tranche("1000")
        opt_in_lender(member=active_member, is_global=False)
        r = _client(active_member).post(
            "/api/v1/savings/me/lender/tranches/",
            {"montant": "15000"},
            format="json",
        )
        assert r.status_code == 201
        assert r.json()["statut"] == "disponible"

    def test_blocked_if_not_lender(self, active_member):
        r = _client(active_member).post(
            "/api/v1/savings/me/lender/tranches/",
            {"montant": "10000"},
            format="json",
        )
        assert r.status_code == 400

    def test_blocked_below_min(self, active_member):
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])
        _set_min_tranche("5000")
        opt_in_lender(member=active_member, is_global=False)
        r = _client(active_member).post(
            "/api/v1/savings/me/lender/tranches/",
            {"montant": "2000"},
            format="json",
        )
        assert r.status_code == 400


# Récupération de tranche membre : endpoint retiré (admin uniquement) — plus de
# test de cancel côté membre.


# ---------------------------------------------------------------------------
# POST /savings/me/lender/funding-requests/<id>/respond/
# ---------------------------------------------------------------------------


class TestFundingRespond:
    def _setup_funding(self, borrower):
        # Borrower distinct du prêteur
        lender = _make_active_lender(mode_global=True, classic_solde=Decimal("200000"))
        loan = _build_loan(borrower, montant=Decimal("50000"))
        fr = request_funding(loan)
        cr = fr.consent_requests.get(lender=lender)
        return lender, cr

    def test_accept_records_response(self, active_member):
        borrower = MemberFactory()
        lender, cr = self._setup_funding(borrower)
        r = _client(lender).post(
            f"/api/v1/savings/me/lender/funding-requests/{cr.id}/respond/",
            {"accept": True},
            format="json",
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["statut"] in ("accepted", "auto_accepted")  # post-settle peut varier
        cr.refresh_from_db()
        assert cr.statut != LenderConsentRequest.Statut.PENDING

    def test_refuse_requires_motif(self, active_member):
        borrower = MemberFactory()
        lender, cr = self._setup_funding(borrower)
        r = _client(lender).post(
            f"/api/v1/savings/me/lender/funding-requests/{cr.id}/respond/",
            {"accept": False},
            format="json",
        )
        assert r.status_code == 400

    def test_refuse_with_motif(self, active_member):
        borrower = MemberFactory()
        lender, cr = self._setup_funding(borrower)
        r = _client(lender).post(
            f"/api/v1/savings/me/lender/funding-requests/{cr.id}/respond/",
            {"accept": False, "motif": "Pas dispo ce mois-ci"},
            format="json",
        )
        assert r.status_code == 200
        cr.refresh_from_db()
        assert cr.statut == LenderConsentRequest.Statut.REFUSED
        assert cr.refus_motif == "Pas dispo ce mois-ci"

    def test_404_for_other_lender(self, active_member):
        borrower = MemberFactory()
        _, cr = self._setup_funding(borrower)
        r = _client(active_member).post(
            f"/api/v1/savings/me/lender/funding-requests/{cr.id}/respond/",
            {"accept": True},
            format="json",
        )
        assert r.status_code == 404
