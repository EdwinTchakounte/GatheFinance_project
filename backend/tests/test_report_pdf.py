"""Rapports PDF — photo coop + relevé membre.

On teste séparément la COLLECTE (agrégation, sans PDF) et le RENDU (bytes PDF
valides), plus les endpoints staff (200 application/pdf + garde RBAC).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.members.models import Member
from apps_coop.members.report_pdf import (
    build_coop_report,
    build_member_statement,
    collect_coop_report_data,
    collect_member_data,
)
from apps_coop.savings.antidated_services import record_antidated_entry
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


def _staff():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m


def _loan(member, *, montant="100000", solde="80000", statut=Loan.Statut.ACTIF):
    lr = LoanRequest.objects.create(
        member=member, montant_demande=Decimal(montant), duree_mois=6,
        motif="x", statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=member, loan_request=lr, numero_dossier="GF-CR-1",
        montant=Decimal(montant), taux_interet=Decimal("0.10"), duree_mois=6,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=Decimal(montant), solde_restant=Decimal(solde),
        statut=statut,
    )


# ---------------------------------------------------------------------------
# Collecte coop
# ---------------------------------------------------------------------------


class TestCollectCoop:
    def test_structure_complete(self):
        data = collect_coop_report_data()
        for key in ("members", "epargne", "credit", "lenders", "queues", "alerts"):
            assert key in data

    def test_compte_les_membres_par_statut(self):
        MemberFactory()  # actif
        s = MemberFactory()
        s.statut = Member.Statut.SUSPENDU
        s.save(update_fields=["statut"])

        data = collect_coop_report_data()
        assert data["members"]["actif"] >= 1
        assert data["members"]["suspendu"] >= 1
        assert data["members"]["total"] == (
            data["members"]["actif"] + data["members"]["suspendu"]
            + data["members"]["temporaire"] + data["members"]["radie"]
        )

    def test_epargne_ne_double_compte_pas_le_placement(self):
        """classique = solde total (placement inclus). L'épargne totale ne doit
        pas compter le placement deux fois."""
        m = MemberFactory()
        SavingsAccount.objects.filter(member=m).update(solde=Decimal("10000"))
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("50000"), date_ouverture=date.today()
        )
        data = collect_coop_report_data()
        # total = collecte + classique (classique inclut déjà le placement).
        assert data["epargne"]["total"] == (
            data["epargne"]["collecte"] + data["epargne"]["classique"]
        )

    def test_encours_credit_agrege_actifs_et_retard(self):
        m = MemberFactory()
        _loan(m, montant="100000", solde="80000", statut=Loan.Statut.ACTIF)
        data = collect_coop_report_data()
        assert data["credit"]["encours"] >= Decimal("80000")
        assert data["credit"]["n_actifs"] >= 1

    def test_reinscription_en_retard_est_une_alerte(self):
        m = MemberFactory()
        m.date_derniere_reinscription = date.today() - timedelta(days=400)
        m.save(update_fields=["date_derniere_reinscription"])
        data = collect_coop_report_data()
        assert data["alerts"]["reinscription_overdue"] >= 1


# ---------------------------------------------------------------------------
# Rendu PDF
# ---------------------------------------------------------------------------


class TestRenderPdf:
    def test_coop_report_est_un_pdf_valide(self):
        MemberFactory()
        pdf = build_coop_report()
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 1500

    def test_coop_report_sur_base_vide_ne_plante_pas(self):
        """Robustesse : aucune donnée → pas de division par zéro sur les
        graphiques (camembert vide filtré)."""
        pdf = build_coop_report()
        assert pdf[:5] == b"%PDF-"

    def test_member_statement_est_un_pdf_valide(self):
        m = MemberFactory()
        SavingsAccount.objects.filter(member=m).update(solde=Decimal("10000"))
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("50000"), date_ouverture=date.today()
        )
        record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("5000"), date_op=date.today() - timedelta(days=10),
        )
        _loan(m)
        pdf = build_member_statement(m)
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 1500

    def test_member_statement_sans_donnee_ne_plante_pas(self):
        m = MemberFactory()
        pdf = build_member_statement(m)
        assert pdf[:5] == b"%PDF-"


class TestCollectMember:
    def test_ecritures_fusionnent_collecte_et_classique(self):
        m = MemberFactory()
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("0"), date_ouverture=date.today()
        )
        record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("3000"), date_op=date.today() - timedelta(days=5),
        )
        record_antidated_entry(
            member=m, product="classique", sens="depot",
            montant=Decimal("7000"), date_op=date.today() - timedelta(days=3),
        )
        data = collect_member_data(m)
        produits = {e["produit"] for e in data["ecritures"]}
        assert "Collecte" in produits and "Classique" in produits


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


class TestEndpoints:
    def _api(self, member):
        c = APIClient()
        c.force_authenticate(user=member.user)
        return c

    def test_coop_report_endpoint_renvoie_un_pdf(self):
        staff = _staff()
        r = self._api(staff).get("/api/v1/admin/report/coop/")
        assert r.status_code == 200
        assert r["Content-Type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"

    def test_member_statement_endpoint_renvoie_un_pdf(self):
        staff = _staff()
        cible = MemberFactory()
        r = self._api(staff).get(f"/api/v1/admin/members/{cible.id}/statement/")
        assert r.status_code == 200
        assert r["Content-Type"] == "application/pdf"

    def test_non_staff_refuse(self):
        membre = MemberFactory()
        r = self._api(membre).get("/api/v1/admin/report/coop/")
        assert r.status_code in (401, 403)

    def test_statement_membre_inconnu_404(self):
        staff = _staff()
        r = self._api(staff).get("/api/v1/admin/members/99999/statement/")
        assert r.status_code == 404
