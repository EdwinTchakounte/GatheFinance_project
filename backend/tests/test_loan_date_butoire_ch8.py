"""CH-8 — Échéancier souple + date butoire obligatoire.

Couvre :
  - ``Loan.date_butoire`` posée par ``approve_loan_request`` (= dernière échéance).
  - Property ``date_limite_globale`` : préfère ``date_butoire``, fallback dernière échéance.
  - Endpoint admin ``/admin/loans/<pk>/extend-deadline/`` :
      * Admin peut étendre avec motif + new > current.
      * Non-admin refusé (403).
      * Validations : motif requis, format date, new > current, statut actif/en_retard.
      * Audit ``loan.deadline_extended`` enregistré.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps_coop.audit.models import AuditLog
from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.services import (
    approve_loan_request,
    generate_installments_flat_interest,
)
from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


User = get_user_model()


@pytest.fixture(autouse=True)
def _reset_factory_sequences():
    # Évite les collisions UNIQUE sur numero_membre quand ce module est exécuté
    # après d'autres modules qui ont incrémenté la séquence Postgres réelle.
    MemberFactory.reset_sequence(900000)
    UserFactory.reset_sequence(900000)
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_active_loan(member, *, suffix="X", duree=3, montant=Decimal("90000")):
    """Crée un Loan ACTIF + ses échéances flat-interest, sans date_butoire."""
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=duree,
        motif="Test CH-8",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    loan = Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier=f"GF-CH8-{suffix}",
        montant=montant,
        taux_interet=Decimal("0.10"),
        duree_mois=duree,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=montant * Decimal("1.10"),
        solde_restant=montant * Decimal("1.10"),
        statut=Loan.Statut.ACTIF,
    )
    generate_installments_flat_interest(loan)
    return loan


# ---------------------------------------------------------------------------
# Property + service : date_butoire est posée à l'approbation.
# ---------------------------------------------------------------------------
class TestDateButoireOnApprove:
    def test_approve_sets_date_butoire_to_last_echeance(self, active_member, comite_user):
        lr = LoanRequest.objects.create(
            member=active_member,
            montant_demande=Decimal("60000"),
            duree_mois=6,
            motif="Test CH-8 approve",
            statut=LoanRequest.Statut.EN_INSTRUCTION,
            modalite_paiement="mensuel",
        )
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        assert loan is not None
        last_echeance = (
            loan.installments.order_by("-date_echeance")
            .values_list("date_echeance", flat=True)
            .first()
        )
        assert last_echeance is not None
        loan.refresh_from_db()
        assert loan.date_butoire == last_echeance

    def test_property_prefers_date_butoire_over_last_echeance(self, active_member):
        loan = _build_active_loan(active_member, suffix="prop")
        last = (
            loan.installments.order_by("-date_echeance")
            .values_list("date_echeance", flat=True)
            .first()
        )
        # Sans date_butoire : fallback dernière échéance.
        assert loan.date_butoire is None
        assert loan.date_limite_globale == last

        # Avec date_butoire posée : priorité absolue (peut différer de la dernière échéance).
        custom = last + timedelta(days=45)
        loan.date_butoire = custom
        loan.save(update_fields=["date_butoire", "updated_at"])
        loan.refresh_from_db()
        assert loan.date_limite_globale == custom


# ---------------------------------------------------------------------------
# Endpoint admin : POST /admin/loans/<pk>/extend-deadline/
# ---------------------------------------------------------------------------
class TestExtendDeadlineEndpoint:
    def test_admin_can_extend_with_motif(self, active_member, admin_user):
        loan = _build_active_loan(active_member, suffix="ext1")
        loan.date_butoire = date.today() + timedelta(days=60)
        loan.save(update_fields=["date_butoire", "updated_at"])

        new_date = loan.date_butoire + timedelta(days=30)
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {"date_butoire": new_date.isoformat(), "motif": "Aléa professionnel."},
            format="json",
        )
        assert r.status_code == 200, r.content
        loan.refresh_from_db()
        assert loan.date_butoire == new_date
        # Audit enregistré.
        assert AuditLog.objects.filter(
            action="loan.deadline_extended",
            entite_type="Loan",
            entite_id=loan.id,
        ).exists()

    def test_non_admin_rejected_403(self, active_member, staff_user):
        loan = _build_active_loan(active_member, suffix="ext2")
        loan.date_butoire = date.today() + timedelta(days=60)
        loan.save(update_fields=["date_butoire", "updated_at"])

        client = APIClient()
        client.force_authenticate(staff_user)
        r = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {
                "date_butoire": (loan.date_butoire + timedelta(days=30)).isoformat(),
                "motif": "test",
            },
            format="json",
        )
        assert r.status_code == 403

    def test_unauthenticated_rejected(self, active_member):
        loan = _build_active_loan(active_member, suffix="ext3")
        client = APIClient()
        r = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {"date_butoire": date.today().isoformat(), "motif": "x"},
            format="json",
        )
        assert r.status_code in (401, 403)

    def test_invalid_date_format_400(self, active_member, admin_user):
        loan = _build_active_loan(active_member, suffix="ext4")
        loan.date_butoire = date.today() + timedelta(days=60)
        loan.save(update_fields=["date_butoire", "updated_at"])

        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {"date_butoire": "31/12/2026", "motif": "test"},
            format="json",
        )
        assert r.status_code == 400
        assert "YYYY-MM-DD" in r.json()["detail"]

    def test_missing_motif_400(self, active_member, admin_user):
        loan = _build_active_loan(active_member, suffix="ext5")
        loan.date_butoire = date.today() + timedelta(days=60)
        loan.save(update_fields=["date_butoire", "updated_at"])

        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {
                "date_butoire": (loan.date_butoire + timedelta(days=30)).isoformat(),
                "motif": "   ",
            },
            format="json",
        )
        assert r.status_code == 400
        assert "Motif" in r.json()["detail"] or "motif" in r.json()["detail"]

    def test_new_date_not_after_current_400(self, active_member, admin_user):
        loan = _build_active_loan(active_member, suffix="ext6")
        loan.date_butoire = date.today() + timedelta(days=60)
        loan.save(update_fields=["date_butoire", "updated_at"])

        client = APIClient()
        client.force_authenticate(admin_user)
        # Égale à l'actuelle → refus.
        r = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {"date_butoire": loan.date_butoire.isoformat(), "motif": "test"},
            format="json",
        )
        assert r.status_code == 400
        # Antérieure → refus.
        r2 = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {
                "date_butoire": (loan.date_butoire - timedelta(days=10)).isoformat(),
                "motif": "test",
            },
            format="json",
        )
        assert r2.status_code == 400

    def test_inactive_loan_rejected_400(self, active_member, admin_user):
        loan = _build_active_loan(active_member, suffix="ext7")
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut", "updated_at"])

        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {
                "date_butoire": (date.today() + timedelta(days=120)).isoformat(),
                "motif": "test",
            },
            format="json",
        )
        assert r.status_code == 400

    def test_en_retard_loan_accepted(self, active_member, admin_user):
        loan = _build_active_loan(active_member, suffix="ext8")
        loan.statut = Loan.Statut.EN_RETARD
        loan.date_butoire = date.today() + timedelta(days=10)
        loan.save(update_fields=["statut", "date_butoire", "updated_at"])

        client = APIClient()
        client.force_authenticate(admin_user)
        new_date = loan.date_butoire + timedelta(days=30)
        r = client.post(
            f"/api/v1/loans/admin/{loan.id}/extend-deadline/",
            {"date_butoire": new_date.isoformat(), "motif": "Accord exceptionnel."},
            format="json",
        )
        assert r.status_code == 200, r.content
        loan.refresh_from_db()
        assert loan.date_butoire == new_date

    def test_not_found_404(self, admin_user):
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(
            "/api/v1/loans/admin/999999/extend-deadline/",
            {"date_butoire": date.today().isoformat(), "motif": "test"},
            format="json",
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------
@pytest.fixture
def comite_user(db):
    """Compte du comité crédit — passe ``IsComite`` (utilisé par approve_loan_request)."""
    from django.contrib.auth.models import Group

    u = User.objects.create_user(
        email="comite-ch8@gathe.test", password="x", username="comite-ch8",
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u
