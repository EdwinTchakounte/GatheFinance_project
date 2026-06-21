"""Tests LOT 16 — Admin CRUD MicrocreditCampaign + décision LR campagne.

Couvre :
- GET    /loans/admin/campaigns/                       — liste + filtres
- POST   /loans/admin/campaigns/                       — création
- GET    /loans/admin/campaigns/<id>/                  — détail enrichi
- PATCH  /loans/admin/campaigns/<id>/close/            — clôture manuelle
- POST   /loans/admin/requests/<id>/campaign-decide/   — comité valide/rejette LR

Les endpoints utilisent ``IsStaff`` (liste/CRUD) et ``IsComite`` (validation LR).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.audit.models import AuditLog
from apps_coop.loans.models import LoanRequest, MicrocreditCampaign


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


@pytest.fixture
def comite_user(db):
    User = get_user_model()
    user = User.objects.create_user(
        username="comite@test.local",
        email="comite@test.local",
        password="testpass1234",
        is_staff=True,
    )
    g, _ = Group.objects.get_or_create(name="comite")
    user.groups.add(g)
    # IsStaff voit aussi 'comite' donc on n'a pas besoin du groupe 'staff'.
    return user


@pytest.fixture
def comite_client(comite_user):
    c = APIClient()
    c.force_authenticate(user=comite_user)
    return c


def _open_campaign(admin_user, *, nom="Test", profil="commercants", days_left=30):
    today = date.today()
    return MicrocreditCampaign.objects.create(
        nom=nom,
        profil_cible=profil,
        date_debut=today - timedelta(days=5),
        date_fin=today + timedelta(days=days_left),
        montant_min=Decimal("5000"),
        montant_max=Decimal("50000"),
        taux_interet=Decimal("0.10"),
        nb_jours_recouvrement=60,
        actif=True,
        created_by=admin_user,
    )


# ---------------------------------------------------------------------------
# GET /loans/admin/campaigns/ — liste + filtres
# ---------------------------------------------------------------------------


class TestList:
    def test_list_empty(self, admin_client):
        r = admin_client.get("/api/v1/loans/admin/campaigns/")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 0
        assert body["results"] == []

    def test_list_returns_campaigns(self, admin_client, admin_user):
        _open_campaign(admin_user, nom="A", profil="commercants")
        _open_campaign(admin_user, nom="B", profil="agriculteurs")
        r = admin_client.get("/api/v1/loans/admin/campaigns/")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 2
        assert {row["nom"] for row in body["results"]} == {"A", "B"}

    def test_filter_actif_false(self, admin_client, admin_user):
        c1 = _open_campaign(admin_user, nom="ouverte")
        c2 = _open_campaign(admin_user, nom="fermee")
        c2.actif = False
        c2.save()
        r = admin_client.get("/api/v1/loans/admin/campaigns/?actif=false")
        body = r.json()
        assert body["count"] == 1
        assert body["results"][0]["nom"] == "fermee"

    def test_filter_profil_cible(self, admin_client, admin_user):
        _open_campaign(admin_user, nom="A", profil="commercants")
        _open_campaign(admin_user, nom="B", profil="agriculteurs")
        r = admin_client.get("/api/v1/loans/admin/campaigns/?profil_cible=commercants")
        body = r.json()
        assert body["count"] == 1
        assert body["results"][0]["nom"] == "A"

    def test_filter_is_open(self, admin_client, admin_user):
        # Une dans la fenêtre, l'autre passée
        c1 = _open_campaign(admin_user, nom="dans-fenetre")
        c2 = MicrocreditCampaign.objects.create(
            nom="passee", profil_cible="x",
            date_debut=date.today() - timedelta(days=60),
            date_fin=date.today() - timedelta(days=5),
            montant_min=0, montant_max=Decimal("10000"),
            taux_interet=Decimal("0.10"), nb_jours_recouvrement=30,
            actif=True, created_by=admin_user,
        )
        r = admin_client.get("/api/v1/loans/admin/campaigns/?is_open=true")
        body = r.json()
        assert body["count"] == 1
        assert body["results"][0]["nom"] == "dans-fenetre"

    def test_requires_staff(self, db, active_member):
        c = APIClient()
        c.force_authenticate(user=active_member.user)
        r = c.get("/api/v1/loans/admin/campaigns/")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /loans/admin/campaigns/ — création
# ---------------------------------------------------------------------------


class TestCreate:
    def _payload(self, **overrides):
        today = date.today()
        body = {
            "nom": "Campagne 2026 Q3",
            "profil_cible": "commercants",
            "date_debut": today.isoformat(),
            "date_fin": (today + timedelta(days=30)).isoformat(),
            "montant_min": "5000",
            "montant_max": "50000",
            "taux_interet": "0.10",
            "nb_jours_recouvrement": 60,
            "plafond_beneficiaires": 50,
        }
        body.update(overrides)
        return body

    def test_create_persists_and_audits(self, admin_client, admin_user):
        r = admin_client.post(
            "/api/v1/loans/admin/campaigns/",
            self._payload(),
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["nom"] == "Campagne 2026 Q3"
        assert body["actif"] is True
        assert body["is_open"] is True

        c = MicrocreditCampaign.objects.get(pk=body["id"])
        assert c.created_by_id == admin_user.id

        assert AuditLog.objects.filter(
            action="microcampaign.created", entite_id=c.id
        ).exists()

    def test_date_fin_before_debut_rejects(self, admin_client):
        today = date.today()
        r = admin_client.post(
            "/api/v1/loans/admin/campaigns/",
            self._payload(
                date_debut=today.isoformat(),
                date_fin=(today - timedelta(days=1)).isoformat(),
            ),
            format="json",
        )
        assert r.status_code == 400
        assert "date_fin" in r.json()

    def test_montant_max_below_min_rejects(self, admin_client):
        r = admin_client.post(
            "/api/v1/loans/admin/campaigns/",
            self._payload(montant_min="50000", montant_max="10000"),
            format="json",
        )
        assert r.status_code == 400
        assert "montant_max" in r.json()

    def test_negative_taux_rejects(self, admin_client):
        r = admin_client.post(
            "/api/v1/loans/admin/campaigns/",
            self._payload(taux_interet="-0.10"),
            format="json",
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /loans/admin/campaigns/<id>/ — détail
# ---------------------------------------------------------------------------


class TestDetail:
    def test_detail_includes_pending_requests(
        self, admin_client, admin_user, active_member
    ):
        c = _open_campaign(admin_user)
        LoanRequest.objects.create(
            member=active_member,
            montant_demande=Decimal("20000"),
            duree_mois=6,
            motif="Achat stock",
            statut=LoanRequest.Statut.EN_VALIDATION_CAMPAGNE,
            microcampaign=c,
        )
        r = admin_client.get(f"/api/v1/loans/admin/campaigns/{c.id}/")
        assert r.status_code == 200
        body = r.json()
        assert body["pending_count"] == 1
        assert body["pending_requests"][0]["montant_demande"] == "20000.00"

    def test_detail_404(self, admin_client):
        r = admin_client.get("/api/v1/loans/admin/campaigns/99999/")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /loans/admin/campaigns/<id>/close/ — clôture
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_sets_actif_false_and_records_reason(self, admin_client, admin_user):
        c = _open_campaign(admin_user)
        r = admin_client.patch(
            f"/api/v1/loans/admin/campaigns/{c.id}/close/",
            {"reason": "quota_reached"},
            format="json",
        )
        assert r.status_code == 200
        body = r.json()
        assert body["actif"] is False
        assert body["close_reason"] == "quota_reached"
        assert body["is_open"] is False

        c.refresh_from_db()
        assert c.actif is False
        assert c.closed_at is not None

    def test_close_idempotent(self, admin_client, admin_user):
        c = _open_campaign(admin_user)
        admin_client.patch(
            f"/api/v1/loans/admin/campaigns/{c.id}/close/",
            {"reason": "manual"},
            format="json",
        )
        # Deuxième appel
        r = admin_client.patch(
            f"/api/v1/loans/admin/campaigns/{c.id}/close/",
            {"reason": "again"},
            format="json",
        )
        assert r.status_code == 200
        c.refresh_from_db()
        # close_reason garde la première valeur (idempotent)
        assert c.close_reason == "manual"

    def test_close_default_reason_manual(self, admin_client, admin_user):
        c = _open_campaign(admin_user)
        r = admin_client.patch(
            f"/api/v1/loans/admin/campaigns/{c.id}/close/", {}, format="json"
        )
        assert r.status_code == 200
        assert r.json()["close_reason"] == "manual"


# ---------------------------------------------------------------------------
# POST /loans/admin/requests/<id>/campaign-decide/ — comité valide/rejette
# ---------------------------------------------------------------------------


class TestCampaignDecide:
    def _make_lr(self, admin_user, active_member, statut=None):
        c = _open_campaign(admin_user)
        return LoanRequest.objects.create(
            member=active_member,
            montant_demande=Decimal("25000"),
            duree_mois=6,
            motif="Stock boutique",
            statut=statut or LoanRequest.Statut.EN_VALIDATION_CAMPAGNE,
            microcampaign=c,
        ), c

    def test_valide_passes_to_en_instruction(
        self, comite_client, admin_user, active_member
    ):
        lr, c = self._make_lr(admin_user, active_member)
        r = comite_client.post(
            f"/api/v1/loans/admin/requests/{lr.id}/campaign-decide/",
            {"decision": "valide"},
            format="json",
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["statut"] == LoanRequest.Statut.EN_INSTRUCTION
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION
        assert AuditLog.objects.filter(
            action="microcampaign.lr_validated", entite_id=lr.id
        ).exists()

    def test_rejete_terminal_with_motif(
        self, comite_client, admin_user, active_member
    ):
        lr, c = self._make_lr(admin_user, active_member)
        r = comite_client.post(
            f"/api/v1/loans/admin/requests/{lr.id}/campaign-decide/",
            {"decision": "rejete", "motif_rejet": "Activité non éligible"},
            format="json",
        )
        assert r.status_code == 200
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.REJETEE_CAMPAGNE
        assert lr.motif_rejet == "Activité non éligible"
        assert lr.date_decision is not None
        assert AuditLog.objects.filter(
            action="microcampaign.lr_rejected", entite_id=lr.id
        ).exists()

    def test_rejet_without_motif_rejects_400(
        self, comite_client, admin_user, active_member
    ):
        lr, c = self._make_lr(admin_user, active_member)
        r = comite_client.post(
            f"/api/v1/loans/admin/requests/{lr.id}/campaign-decide/",
            {"decision": "rejete"},
            format="json",
        )
        assert r.status_code == 400
        assert "motif_rejet" in r.json()

    def test_lr_not_in_campagne_status_rejects(
        self, comite_client, admin_user, active_member
    ):
        lr, c = self._make_lr(
            admin_user, active_member, statut=LoanRequest.Statut.EN_ATTENTE
        )
        r = comite_client.post(
            f"/api/v1/loans/admin/requests/{lr.id}/campaign-decide/",
            {"decision": "valide"},
            format="json",
        )
        assert r.status_code == 400
        assert "validation campagne" in r.json()["detail"].lower()

    def test_requires_comite(self, db, admin_user, active_member):
        lr, c = self._make_lr(admin_user, active_member)
        # Membre standard (non comité)
        c2 = APIClient()
        c2.force_authenticate(user=active_member.user)
        r = c2.post(
            f"/api/v1/loans/admin/requests/{lr.id}/campaign-decide/",
            {"decision": "valide"},
            format="json",
        )
        assert r.status_code == 403

    def test_not_found(self, comite_client):
        r = comite_client.post(
            "/api/v1/loans/admin/requests/99999/campaign-decide/",
            {"decision": "valide"},
            format="json",
        )
        assert r.status_code == 404
