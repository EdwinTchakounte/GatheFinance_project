"""Tests entretien d'admission (Art. 3) + mise en demeure (Art. 13)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.members.services import approve_membership_request

from tests.factories import MembershipRequestFactory


pytestmark = pytest.mark.django_db


class TestAdmissionInterview:
    def test_approve_blocked_without_interview(self, admin_user):
        req = MembershipRequestFactory(date_entretien=None, entretien_favorable=None)
        with pytest.raises(ValueError, match="(?i)entretien"):
            approve_membership_request(req, instructed_by=admin_user, nom="Kamga")

    def test_approve_ok_after_interview(self, admin_user):
        req = MembershipRequestFactory(date_entretien=None)
        # endpoint entretien
        from django.test import Client

        c = Client()
        c.force_login(admin_user)
        r = c.post(
            f"/api/v1/admin/membership-requests/{req.id}/interview/",
            data={"avis": "Sérieux, dossier complet", "favorable": True},
            content_type="application/json",
        )
        assert r.status_code == 200, r.content
        req.refresh_from_db()
        assert req.date_entretien is not None
        assert req.entretien_favorable is True
        # désormais l'approbation passe
        member = approve_membership_request(req, instructed_by=admin_user, nom="Kamga")
        assert member is not None


class TestLoanNotice:
    def _late_loan(self, member):
        lr = LoanRequest.objects.create(
            member=member,
            montant_demande=Decimal("100000"),
            duree_mois=3,
            motif="x",
            statut=LoanRequest.Statut.APPROUVEE,
        )
        return Loan.objects.create(
            member=member,
            loan_request=lr,
            numero_dossier="GF-CR-NOTICE-1",
            montant=Decimal("100000"),
            taux_interet=Decimal("0.10"),
            duree_mois=3,
            date_decaissement=date.today() - timedelta(days=120),
            date_premiere_echeance=date.today() - timedelta(days=90),
            montant_total_du=Decimal("110000"),
            solde_restant=Decimal("110000"),
            statut=Loan.Statut.EN_RETARD,
        )

    def test_notice_on_late_loan(self, client, active_member, admin_user):
        loan = self._late_loan(active_member)
        client.force_login(admin_user)
        r = client.post(f"/api/v1/loans/admin/{loan.id}/notice/")
        assert r.status_code == 200, r.content
        assert r.json()["mise_en_demeure_count"] == 1
        loan.refresh_from_db()
        assert loan.mise_en_demeure_at is not None

    def test_notice_increments(self, client, active_member, admin_user):
        loan = self._late_loan(active_member)
        client.force_login(admin_user)
        client.post(f"/api/v1/loans/admin/{loan.id}/notice/")
        r2 = client.post(f"/api/v1/loans/admin/{loan.id}/notice/")
        assert r2.json()["mise_en_demeure_count"] == 2

    def test_notice_refused_on_active_loan(self, client, active_member, admin_user):
        loan = self._late_loan(active_member)
        loan.statut = Loan.Statut.ACTIF
        loan.save(update_fields=["statut"])
        client.force_login(admin_user)
        r = client.post(f"/api/v1/loans/admin/{loan.id}/notice/")
        assert r.status_code == 400
