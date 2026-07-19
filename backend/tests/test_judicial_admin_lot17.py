"""Tests LOT 17 — Admin CRUD JudicialEscalation.

Couvre les 6 endpoints HTTP du module ``judicial_admin.py`` :
  GET    /loans/admin/escalations/
  GET    /loans/admin/escalations/<id>/
  POST   /loans/admin/loans/<loan_id>/escalation/
  POST   /loans/admin/escalations/<id>/decision/
  POST   /loans/admin/escalations/<id>/execution/
  POST   /loans/admin/escalations/<id>/classer/

Permission : ``IsAdmin`` pour les mutations (open/decision/execution/classer),
``IsStaff`` pour les lectures.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from apps_coop.loans.models import (
    JudicialEscalation,
    Loan,
    LoanRequest,
)
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _build_loan_with_pursuit(
    *,
    member=None,
    solde_restant=Decimal("50000"),
    poursuite_days_ago=70,
):
    m = member or MemberFactory()
    lr = LoanRequest.objects.create(
        member=m,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test escalade",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=m,
        loan_request=lr,
        numero_dossier=f"LOT17-{m.numero_membre}-{solde_restant}",
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        taux_penalite=Decimal("0.50"),
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=poursuite_days_ago + 30),
        date_premiere_echeance=date.today() - timedelta(days=poursuite_days_ago + 20),
        montant_total_du=Decimal("110000"),
        solde_restant=solde_restant,
        statut=Loan.Statut.CONTENTIEUX,
        epargne_saisie_at=timezone.now() - timedelta(days=poursuite_days_ago + 1),
        epargne_saisie_montant=Decimal("60000"),
        poursuite_judiciaire_at=timezone.now() - timedelta(days=poursuite_days_ago),
    )


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


@pytest.fixture
def staff_client(db):
    User = get_user_model()
    u = User.objects.create_user(
        username="staff17@test.local",
        email="staff17@test.local",
        password="testpass1234",
        is_staff=True,
    )
    g, _ = Group.objects.get_or_create(name="staff")
    u.groups.add(g)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


# ---------------------------------------------------------------------------
# POST /loans/admin/loans/<loan_id>/escalation/ — ouverture
# ---------------------------------------------------------------------------


class TestOpen:
    def test_creates_in_instance(self, admin_client, admin_user):
        loan = _build_loan_with_pursuit()
        r = admin_client.post(
            f"/api/v1/loans/admin/loans/{loan.id}/escalation/",
            {"motif": "Mise en demeure restée sans réponse.", "mode": "manual"},
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["statut"] == JudicialEscalation.Statut.EN_INSTANCE
        assert body["loan_id"] == loan.id
        assert body["declenche_par_id"] == admin_user.id

    def test_idempotent_returns_200(self, admin_client):
        loan = _build_loan_with_pursuit()
        r1 = admin_client.post(
            f"/api/v1/loans/admin/loans/{loan.id}/escalation/",
            {"motif": "Première ouverture"},
            format="json",
        )
        assert r1.status_code == 201
        r2 = admin_client.post(
            f"/api/v1/loans/admin/loans/{loan.id}/escalation/",
            {"motif": "Deuxième tentative — sera ignorée"},
            format="json",
        )
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]

    def test_guard_solde_zero_rejects(self, admin_client):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("0"))
        r = admin_client.post(
            f"/api/v1/loans/admin/loans/{loan.id}/escalation/",
            {"motif": "Test"},
            format="json",
        )
        assert r.status_code == 400
        assert "reliquat" in r.json()["detail"].lower()

    def test_guard_no_poursuite_rejects(self, admin_client):
        m = MemberFactory()
        lr = LoanRequest.objects.create(
            member=m,
            montant_demande=Decimal("100000"),
            duree_mois=3,
            motif="test",
            statut=LoanRequest.Statut.APPROUVEE,
        )
        loan = Loan.objects.create(
            member=m,
            loan_request=lr,
            numero_dossier="NO-POURSUITE",
            montant=Decimal("100000"),
            taux_interet=Decimal("0.10"),
            duree_mois=3,
            date_decaissement=date.today() - timedelta(days=30),
            date_premiere_echeance=date.today() - timedelta(days=20),
            montant_total_du=Decimal("110000"),
            solde_restant=Decimal("50000"),
            statut=Loan.Statut.ACTIF,
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/loans/{loan.id}/escalation/",
            {"motif": "Test"},
            format="json",
        )
        assert r.status_code == 400
        assert "saisie" in r.json()["detail"].lower()

    def test_loan_not_found(self, admin_client):
        r = admin_client.post(
            "/api/v1/loans/admin/loans/99999/escalation/",
            {"motif": "Test"},
            format="json",
        )
        assert r.status_code == 404

    def test_requires_admin(self, staff_client, db):
        # staff sans is_superuser ni groupe coop_admin → 403
        loan = _build_loan_with_pursuit()
        r = staff_client.post(
            f"/api/v1/loans/admin/loans/{loan.id}/escalation/",
            {"motif": "Test"},
            format="json",
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /loans/admin/escalations/ — liste + filtres
# ---------------------------------------------------------------------------


class TestList:
    def _make_escalation(
        self, statut=JudicialEscalation.Statut.EN_INSTANCE, member=None
    ):
        loan = _build_loan_with_pursuit(member=member)
        return JudicialEscalation.objects.create(
            loan=loan,
            statut=statut,
            motif="test list",
            declenche_mode="manual",
        )

    def test_list_returns_all(self, staff_client):
        self._make_escalation()
        self._make_escalation()
        r = staff_client.get("/api/v1/loans/admin/escalations/")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 2

    def test_filter_open_excludes_terminal(self, staff_client):
        self._make_escalation(statut=JudicialEscalation.Statut.EN_INSTANCE)
        e2 = self._make_escalation(statut=JudicialEscalation.Statut.EXECUTEE)
        e3 = self._make_escalation(
            statut=JudicialEscalation.Statut.CLASSEE_SANS_SUITE
        )
        r = staff_client.get("/api/v1/loans/admin/escalations/?open=true")
        body = r.json()
        # Seul EN_INSTANCE et DECISION_RENDUE sont "open" → 1 dans cette suite.
        assert body["count"] == 1

    def test_filter_by_statut(self, staff_client):
        self._make_escalation(statut=JudicialEscalation.Statut.EN_INSTANCE)
        self._make_escalation(statut=JudicialEscalation.Statut.DECISION_RENDUE)
        r = staff_client.get(
            "/api/v1/loans/admin/escalations/?statut=decision_rendue"
        )
        body = r.json()
        assert body["count"] == 1
        assert body["results"][0]["statut"] == "decision_rendue"

    def test_filter_by_member(self, staff_client):
        m1 = MemberFactory(nom="ALPHA")
        m2 = MemberFactory(nom="BETA")
        self._make_escalation(member=m1)
        self._make_escalation(member=m2)
        r = staff_client.get(f"/api/v1/loans/admin/escalations/?member={m1.id}")
        body = r.json()
        assert body["count"] == 1

    def test_search_q(self, staff_client):
        m = MemberFactory(nom="DUPONT_UNIQUE")
        self._make_escalation(member=m)
        self._make_escalation()
        r = staff_client.get(
            "/api/v1/loans/admin/escalations/?q=DUPONT_UNIQUE"
        )
        body = r.json()
        assert body["count"] == 1


# ---------------------------------------------------------------------------
# GET /loans/admin/escalations/<id>/ — détail
# ---------------------------------------------------------------------------


class TestDetail:
    def test_detail_returns_escalation(self, staff_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan, motif="détail", declenche_mode="manual"
        )
        r = staff_client.get(f"/api/v1/loans/admin/escalations/{e.id}/")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == e.id
        assert body["loan_id"] == loan.id

    def test_detail_404(self, staff_client):
        r = staff_client.get("/api/v1/loans/admin/escalations/99999/")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /loans/admin/escalations/<id>/decision/ — phase E1
# ---------------------------------------------------------------------------


class TestDecision:
    def test_records_decision_with_biens(self, admin_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan, motif="X", declenche_mode="manual"
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/decision/",
            {
                "decision_date": date.today().isoformat(),
                "biens_saisissables": [
                    {"description": "Mobylette", "valeur_estimee": "120000"},
                    {"description": "TV", "valeur_estimee": "50000"},
                ],
            },
            format="json",
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["statut"] == "decision_rendue"
        assert body["decision_date"] == date.today().isoformat()
        assert len(body["biens_saisissables"]) == 2

    def test_decision_idempotent(self, admin_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan,
            motif="X",
            declenche_mode="manual",
            statut=JudicialEscalation.Statut.DECISION_RENDUE,
            decision_date=date.today() - timedelta(days=2),
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/decision/",
            {
                "decision_date": date.today().isoformat(),
                "biens_saisissables": [],
            },
            format="json",
        )
        assert r.status_code == 200
        # decision_date d'origine conservée
        e.refresh_from_db()
        assert e.decision_date == date.today() - timedelta(days=2)

    def test_decision_rejects_if_terminal(self, admin_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan,
            motif="X",
            declenche_mode="manual",
            statut=JudicialEscalation.Statut.EXECUTEE,
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/decision/",
            {"decision_date": date.today().isoformat()},
            format="json",
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /loans/admin/escalations/<id>/execution/ — phase E2
# ---------------------------------------------------------------------------


class TestExecution:
    def test_records_execution_and_decrements_solde(self, admin_client):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("50000"))
        e = JudicialEscalation.objects.create(
            loan=loan,
            motif="X",
            declenche_mode="manual",
            statut=JudicialEscalation.Statut.DECISION_RENDUE,
            decision_date=date.today() - timedelta(days=1),
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/execution/",
            {
                "execution_date": date.today().isoformat(),
                "montant_recouvre": "30000",
                "biens_saisis": [
                    {"description": "Mobylette", "valeur_estimee": "120000"},
                ],
            },
            format="json",
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["statut"] == "executee"
        assert Decimal(body["montant_recouvre"]) == Decimal("30000")
        # Solde décrémenté
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("20000")
        # Crédit toujours ACTIF/CONTENTIEUX (pas à zéro)
        assert loan.statut == Loan.Statut.CONTENTIEUX

    def test_execution_full_recouvrement_closes_loan(self, admin_client):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("30000"))
        e = JudicialEscalation.objects.create(
            loan=loan,
            motif="X",
            declenche_mode="manual",
            statut=JudicialEscalation.Statut.DECISION_RENDUE,
            decision_date=date.today() - timedelta(days=1),
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/execution/",
            {
                "execution_date": date.today().isoformat(),
                "montant_recouvre": "30000",
            },
            format="json",
        )
        assert r.status_code == 200
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("0")
        assert loan.statut == Loan.Statut.CLOTURE

    def test_execution_clamps_overshoot(self, admin_client):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("20000"))
        e = JudicialEscalation.objects.create(
            loan=loan,
            motif="X",
            declenche_mode="manual",
            statut=JudicialEscalation.Statut.DECISION_RENDUE,
            decision_date=date.today() - timedelta(days=1),
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/execution/",
            {
                "execution_date": date.today().isoformat(),
                "montant_recouvre": "999999",
            },
            format="json",
        )
        assert r.status_code == 200
        loan.refresh_from_db()
        # Pas de solde négatif — clampé à 0.
        assert loan.solde_restant == Decimal("0")
        body = r.json()
        assert Decimal(body["montant_recouvre"]) == Decimal("20000")

    def test_execution_requires_decision_first(self, admin_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan,
            motif="X",
            declenche_mode="manual",
            statut=JudicialEscalation.Statut.EN_INSTANCE,
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/execution/",
            {
                "execution_date": date.today().isoformat(),
                "montant_recouvre": "10000",
            },
            format="json",
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /loans/admin/escalations/<id>/classer/ — abandon
# ---------------------------------------------------------------------------


class TestClasser:
    def test_classer_from_en_instance(self, admin_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan, motif="X", declenche_mode="manual"
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/classer/",
            {"motif": "Débiteur introuvable, abandon."},
            format="json",
        )
        assert r.status_code == 200
        body = r.json()
        assert body["statut"] == "classee_sans_suite"
        assert body["close_reason"] == "irrecouvrable"

    def test_classer_from_decision_rendue(self, admin_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan,
            motif="X",
            declenche_mode="manual",
            statut=JudicialEscalation.Statut.DECISION_RENDUE,
            decision_date=date.today() - timedelta(days=1),
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/classer/",
            {"motif": "Saisie biens impossible."},
            format="json",
        )
        assert r.status_code == 200
        assert r.json()["statut"] == "classee_sans_suite"

    def test_classer_rejects_if_executee(self, admin_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan,
            motif="X",
            declenche_mode="manual",
            statut=JudicialEscalation.Statut.EXECUTEE,
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/classer/",
            {"motif": "test"},
            format="json",
        )
        assert r.status_code == 400

    def test_classer_requires_motif(self, admin_client):
        loan = _build_loan_with_pursuit()
        e = JudicialEscalation.objects.create(
            loan=loan, motif="X", declenche_mode="manual"
        )
        r = admin_client.post(
            f"/api/v1/loans/admin/escalations/{e.id}/classer/",
            {},
            format="json",
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Candidats à l'escalade — la porte d'entrée qui manquait
# ---------------------------------------------------------------------------


class TestEscalationCandidates:
    """En mode `manual` (le défaut), aucune escalade ne naît toute seule : le
    cron d'auto-escalade est désactivé. L'admin doit donc pouvoir en ouvrir
    une — encore faut-il qu'il sache SUR QUEL crédit. Sans cette liste, la
    page Escalades restait vide sans explication.
    """

    def test_liste_les_credits_eligibles(self, staff_client):
        loan = _build_loan_with_pursuit()

        r = staff_client.get("/api/v1/loans/admin/escalations/candidates/")
        assert r.status_code == 200, r.content
        body = r.json()

        assert body["count"] == 1
        row = body["results"][0]
        assert row["loan_id"] == loan.id
        assert row["numero_dossier"] == loan.numero_dossier
        assert row["solde_restant"] == "50000.00"
        assert row["poursuite_judiciaire_at"] is not None

    def test_exclut_les_credits_sans_saisie_epargne(self, staff_client):
        """`poursuite_judiciaire_at` NULL → le service refuserait l'ouverture."""
        loan = _build_loan_with_pursuit()
        Loan.objects.filter(pk=loan.pk).update(poursuite_judiciaire_at=None)

        r = staff_client.get("/api/v1/loans/admin/escalations/candidates/")
        assert r.json()["count"] == 0

    def test_exclut_les_credits_soldes(self, staff_client):
        loan = _build_loan_with_pursuit()
        Loan.objects.filter(pk=loan.pk).update(solde_restant=Decimal("0"))

        r = staff_client.get("/api/v1/loans/admin/escalations/candidates/")
        assert r.json()["count"] == 0

    def test_exclut_ceux_qui_ont_deja_une_escalade(self, staff_client, admin_client):
        loan = _build_loan_with_pursuit()
        admin_client.post(
            f"/api/v1/loans/admin/loans/{loan.id}/escalation/",
            {"motif": "Reliquat impayé."},
            format="json",
        )

        r = staff_client.get("/api/v1/loans/admin/escalations/candidates/")
        assert r.json()["count"] == 0

    def test_ouverture_puis_apparition_dans_la_liste(self, staff_client, admin_client):
        """Bout en bout : c'est ce parcours qui était impossible côté admin."""
        loan = _build_loan_with_pursuit()

        # La page est vide au départ — d'où le symptôme constaté.
        assert staff_client.get(
            "/api/v1/loans/admin/escalations/?open=true"
        ).json()["count"] == 0

        r = admin_client.post(
            f"/api/v1/loans/admin/loans/{loan.id}/escalation/",
            {"motif": "Reliquat après saisie épargne."},
            format="json",
        )
        assert r.status_code == 201, r.content

        listing = staff_client.get(
            "/api/v1/loans/admin/escalations/?open=true"
        ).json()
        assert listing["count"] == 1
        assert listing["results"][0]["loan_numero_dossier"] == loan.numero_dossier
        assert listing["results"][0]["statut"] == JudicialEscalation.Statut.EN_INSTANCE
