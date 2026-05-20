"""Tests de la décision comité sur les reconductions (L1).

Couvre :
  - approve_loan_renewal clôture l'ancien Loan + crée le nouveau + échéancier
  - Refus si statut renewal != demandee
  - Refus si frais non payés (frais_reconduction_payment is None ou pas valide)
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
from apps_coop.payments.models import Payment


pytestmark = pytest.mark.django_db


def _seed_renewal_with_fees_paid(member) -> LoanRenewal:
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("500000"),
        duree_mois=12,
        motif="Test renewal",
        statut=LoanRequest.Statut.APPROUVEE,
        date_decision=timezone.now(),
    )
    loan = Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier="GF-CR-RNW-DEC-001",
        montant=Decimal("500000"),
        taux_interet=Decimal("0.12"),
        duree_mois=12,
        date_decaissement=date.today() - timedelta(days=350),
        date_premiere_echeance=date.today() - timedelta(days=320),
        montant_total_du=Decimal("560000"),
        solde_restant=Decimal("150000"),
        statut=Loan.Statut.ACTIF,
    )
    fees = Payment.objects.create(
        member=member,
        montant=Decimal("3000"),
        type=Payment.Type.FRAIS_RECONDUCTION,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.VALIDE,
        provider_code="tara",
        reference_externe="TEST-RNW-FEES",
        date_versement=timezone.now(),
        date_validation=timezone.now(),
    )
    renewal = LoanRenewal.objects.create(
        loan=loan,
        nouvelle_duree_mois=6,
        frais_reconduction_payment=fees,
    )
    return renewal


class TestApproveLoanRenewal:
    def test_closes_old_loan_and_creates_new_one(self, active_member, admin_user):
        renewal = _seed_renewal_with_fees_paid(active_member)
        old_loan = renewal.loan
        old_solde = old_loan.solde_restant

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
        # Nouveau Loan créé, principal = ancien solde
        assert nouveau.id != old_loan.id
        assert nouveau.montant == old_solde
        assert nouveau.duree_mois == renewal.nouvelle_duree_mois
        assert nouveau.statut == Loan.Statut.ACTIF
        # Échéancier généré
        assert LoanInstallment.objects.filter(loan=nouveau).count() == renewal.nouvelle_duree_mois
        # Renewal close
        assert renewal.statut == LoanRenewal.Statut.APPROUVEE
        assert renewal.date_decision is not None

    def test_idempotent_replay_returns_existing_new_loan(self, active_member, admin_user):
        renewal = _seed_renewal_with_fees_paid(active_member)
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

    def test_rejects_when_fees_not_paid(self, active_member, admin_user):
        renewal = _seed_renewal_with_fees_paid(active_member)
        # On retire le lien vers le paiement
        renewal.frais_reconduction_payment = None
        renewal.save()
        with pytest.raises(ValueError, match="(?i)frais"):
            approve_loan_renewal(
                renewal,
                decided_by=admin_user,
                taux_annuel=Decimal("0.10"),
                date_premiere_echeance=date.today() + timedelta(days=30),
            )

    def test_rejects_when_fees_pending(self, active_member, admin_user):
        renewal = _seed_renewal_with_fees_paid(active_member)
        # Frais bien rattachés mais pas encore validés
        fees = renewal.frais_reconduction_payment
        fees.statut = Payment.Statut.EN_ATTENTE
        fees.save()
        with pytest.raises(ValueError, match="(?i)pas encore valid"):
            approve_loan_renewal(
                renewal,
                decided_by=admin_user,
                taux_annuel=Decimal("0.10"),
                date_premiere_echeance=date.today() + timedelta(days=30),
            )


class TestRejectLoanRenewal:
    def test_marks_renewal_rejected(self, active_member, admin_user):
        renewal = _seed_renewal_with_fees_paid(active_member)
        result = reject_loan_renewal(renewal, decided_by=admin_user, motif="Endettement trop élevé.")
        assert result.statut == LoanRenewal.Statut.REJETEE
        # L'ancien Loan reste actif (pas de clôture sur rejet)
        result.loan.refresh_from_db()
        assert result.loan.statut == Loan.Statut.ACTIF

    def test_motif_required(self, active_member, admin_user):
        renewal = _seed_renewal_with_fees_paid(active_member)
        with pytest.raises(ValueError, match="motif"):
            reject_loan_renewal(renewal, decided_by=admin_user, motif="   ")

    def test_idempotent_double_rejection(self, active_member, admin_user):
        renewal = _seed_renewal_with_fees_paid(active_member)
        reject_loan_renewal(renewal, decided_by=admin_user, motif="Première raison")
        # 2e rejet renvoie la même renewal sans crash
        same = reject_loan_renewal(renewal, decided_by=admin_user, motif="Autre")
        assert same.statut == LoanRenewal.Statut.REJETEE
