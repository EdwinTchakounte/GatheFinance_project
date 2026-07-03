"""Tests de la décision comité sur les reconductions (L1).

Couvre :
  - approve_loan_renewal clôture l'ancien Loan + crée le nouveau + échéancier
  - Aucun frais requis : l'approbation ne dépend d'aucun paiement (Règlement)
  - reject_loan_renewal pose statut + motif obligatoire
  - Idempotence sur déjà-rejetée / déjà-approuvée
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.loans.models import Loan, LoanInstallment, LoanRenewal, LoanRequest
from apps_coop.loans.services import approve_loan_renewal, reject_loan_renewal


pytestmark = pytest.mark.django_db


def _seed_renewal(member) -> LoanRenewal:
    """Crédit actif (90 000, mensuel, 3 mois) avec 1 échéance payée sur 3.

    → capital restant = 60 000, intérêts restants = 6 000 (cf. l'exemple validé
    avec l'utilisateur). Une LoanRenewal `demandee` sans aucun frais.
    """
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("90000"),
        duree_mois=3,
        modalite_paiement="mensuel",
        motif="Test renewal",
        statut=LoanRequest.Statut.APPROUVEE,
        date_decision=timezone.now(),
    )
    loan = Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier="GF-CR-RNW-DEC-001",
        montant=Decimal("90000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        modalite_paiement="mensuel",
        date_decaissement=date.today() - timedelta(days=60),
        date_premiere_echeance=date.today() - timedelta(days=30),
        montant_total_du=Decimal("99000"),
        solde_restant=Decimal("66000"),
        statut=Loan.Statut.ACTIF,
    )
    # 3 échéances de 33 000 (capital 30 000 + intérêts 3 000), la 1re payée.
    for i in range(1, 4):
        LoanInstallment.objects.create(
            loan=loan,
            numero_echeance=i,
            date_echeance=date.today() + timedelta(days=30 * (i - 2)),
            montant_capital=Decimal("30000"),
            montant_interets=Decimal("3000"),
            montant_total=Decimal("33000"),
            montant_paye=Decimal("33000") if i == 1 else Decimal("0"),
            statut=(
                LoanInstallment.Statut.PAYEE if i == 1 else LoanInstallment.Statut.A_VENIR
            ),
        )
    # +1 mois fixe (Article 10), aucun frais rattaché.
    return LoanRenewal.objects.create(loan=loan, nouvelle_duree_mois=1)


class TestApproveLoanRenewal:
    def test_closes_old_loan_and_creates_new_one(self, active_member, admin_user):
        renewal = _seed_renewal(active_member)
        old_loan = renewal.loan

        nouveau = approve_loan_renewal(
            renewal,
            decided_by=admin_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )

        old_loan.refresh_from_db()
        renewal.refresh_from_db()

        # Ancien Loan clôturé
        assert old_loan.statut == Loan.Statut.CLOTURE
        # Nouveau Loan : base = capital restant 60 000 + intérêts restants 6 000.
        assert nouveau.id != old_loan.id
        assert nouveau.montant == Decimal("66000")
        # Au comptant (10 %) : dû = 60 000 + 6 000 + 10 % × 60 000 = 72 000.
        assert nouveau.montant_total_du == Decimal("72000")
        assert nouveau.solde_restant == Decimal("72000")
        assert nouveau.duree_mois == renewal.nouvelle_duree_mois
        assert nouveau.statut == Loan.Statut.ACTIF
        # Crédit issu d'une reconduction → non reconductible à nouveau.
        assert nouveau.issu_reconduction is True
        # Échéancier généré (mensuel +1 mois = 1 échéance)
        assert LoanInstallment.objects.filter(loan=nouveau).count() == renewal.nouvelle_duree_mois
        # Renewal close
        assert renewal.statut == LoanRenewal.Statut.APPROUVEE
        assert renewal.date_decision is not None

    def test_idempotent_replay_returns_existing_new_loan(self, active_member, admin_user):
        renewal = _seed_renewal(active_member)
        n1 = approve_loan_renewal(
            renewal,
            decided_by=admin_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # 2e appel doit retomber sur le même Loan créé
        n2 = approve_loan_renewal(
            renewal,
            decided_by=admin_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        assert n1.id == n2.id

    def test_approval_needs_no_fee_payment(self, active_member, admin_user):
        """La reconduction est sans frais : l'approbation aboutit sans paiement."""
        renewal = _seed_renewal(active_member)
        assert renewal.frais_reconduction_payment_id is None
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=admin_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        renewal.refresh_from_db()
        assert renewal.statut == LoanRenewal.Statut.APPROUVEE
        assert nouveau.statut == Loan.Statut.ACTIF

    def test_reporte_rate_15_percent(self, active_member, admin_user):
        """Reporté (15 %) : 60 000 + 6 000 reportés + 15 % × 60 000 = 75 000."""
        renewal = _seed_renewal(active_member)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=admin_user,
            taux_annuel=Decimal("0.15"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        assert nouveau.montant == Decimal("66000")
        assert nouveau.montant_total_du == Decimal("75000")

    def test_renewed_loan_cannot_be_renewed_again(self, active_member, admin_user):
        """Une seule reconduction par crédit : le crédit issu d'une reconduction
        ne peut pas être reconduit à son tour (bloqué dès la soumission)."""
        from apps_coop.loans.services import request_loan_renewal

        renewal = _seed_renewal(active_member)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=admin_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        assert nouveau.issu_reconduction is True
        with pytest.raises(ValueError, match="(?i)une seule fois|issu d'une reconduction"):
            request_loan_renewal(nouveau)


class TestAdminRenewalEndpoints:
    """Parité mobile↔admin : le membre demande la reconduction (mobile/portail),
    l'admin la voit dans la file et la décide via l'API admin."""

    def test_admin_list_shows_pending_renewal(self, client, active_member, admin_user):
        renewal = _seed_renewal(active_member)
        client.force_login(admin_user)
        r = client.get("/api/v1/loans/admin/renewals/?statut=demandee")
        assert r.status_code == 200, r.content
        rows = r.json()["results"]
        row = next((x for x in rows if x["id"] == renewal.id), None)
        assert row is not None
        assert row["statut"] == "demandee"
        assert row["numero_dossier"] == renewal.loan.numero_dossier
        assert row["member_nom"]
        assert row["solde_restant"] == "66000.00"

    def test_admin_list_requires_staff(self, client, active_member):
        _seed_renewal(active_member)
        client.force_login(active_member.user)
        r = client.get("/api/v1/loans/admin/renewals/")
        assert r.status_code in (401, 403)

    def test_admin_decide_approve_via_api(self, client, active_member, admin_user):
        renewal = _seed_renewal(active_member)
        client.force_login(admin_user)
        r = client.post(
            f"/api/v1/loans/renewals/{renewal.id}/decide/",
            data={
                "decision": "approuvee",
                "taux_annuel": "0.10",
                "date_premiere_echeance": (date.today() + timedelta(days=30)).isoformat(),
            },
            content_type="application/json",
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["decision"] == "approuvee"
        assert body["nouveau_dossier"]
        renewal.refresh_from_db()
        assert renewal.statut == LoanRenewal.Statut.APPROUVEE


class TestRejectLoanRenewal:
    def test_marks_renewal_rejected(self, active_member, admin_user):
        renewal = _seed_renewal(active_member)
        result = reject_loan_renewal(renewal, decided_by=admin_user, motif="Endettement trop élevé.")
        assert result.statut == LoanRenewal.Statut.REJETEE
        # L'ancien Loan reste actif (pas de clôture sur rejet)
        result.loan.refresh_from_db()
        assert result.loan.statut == Loan.Statut.ACTIF

    def test_motif_required(self, active_member, admin_user):
        renewal = _seed_renewal(active_member)
        with pytest.raises(ValueError, match="motif"):
            reject_loan_renewal(renewal, decided_by=admin_user, motif="   ")

    def test_idempotent_double_rejection(self, active_member, admin_user):
        renewal = _seed_renewal(active_member)
        reject_loan_renewal(renewal, decided_by=admin_user, motif="Première raison")
        # 2e rejet renvoie la même renewal sans crash
        same = reject_loan_renewal(renewal, decided_by=admin_user, motif="Autre")
        assert same.statut == LoanRenewal.Statut.REJETEE
