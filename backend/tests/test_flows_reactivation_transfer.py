"""Flows complets (multi-étapes) des lots 2026-07.

  A. Réactivation payante : un membre SUSPENDU qui règle le frais manquant
     depuis son compte redevient ACTIF (les 3 frais réglés → activation).
  B. Transfert : rembourser intégralement un crédit depuis l'épargne le
     bascule en CLOTURE (imputation sur échéance + solde restant à 0).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.transfer_services import (
    repay_loan_from_frozen,
    repay_loan_from_savings,
)
from apps_coop.members.fee_from_savings_services import (
    pay_membership_fee_from_savings,
)
from apps_coop.members.models import Member
from apps_coop.payments.models import FeeType, Payment
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _fee(code, montant):
    FeeType.objects.update_or_create(
        code=code, defaults={"montant": Decimal(montant), "actif": True, "libelle": code}
    )


def _paid(member, ptype):
    now = timezone.now()
    Payment.objects.create(
        member=member, montant=Decimal("2000"), type=ptype,
        source=Payment.Source.MANUEL, statut=Payment.Statut.VALIDE,
        date_versement=now, date_validation=now,
    )


class TestReactivationFlow:
    def test_suspendu_reactive_avec_le_seul_frais_adhesion(self):
        """Décision G5 : la réactivation est basée UNIQUEMENT sur l'adhésion.

        Un membre SUSPENDU (cycle échu) qui re-paie son adhésion depuis son
        compte redevient ACTIF — sans exiger inscription ni carnet.
        """
        _fee("ADHESION", "10000")
        m = MemberFactory()
        # Déjà activé une fois : ses 3 frais ont été soldés (cycle précédent).
        _paid(m, Payment.Type.FRAIS_ADHESION)
        _paid(m, Payment.Type.FRAIS_INSCRIPTION)
        _paid(m, Payment.Type.FRAIS_CARNET)
        m.statut = Member.Statut.SUSPENDU
        m.date_derniere_reinscription = date.today() - timedelta(days=400)
        m.save(update_fields=["statut", "date_derniere_reinscription"])
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("30000"), date_ouverture=date.today()
        )

        # Re-paie l'adhésion (seule) depuis le compte → réactivation.
        pay_membership_fee_from_savings(m, "ADHESION")

        m.refresh_from_db()
        assert m.statut == Member.Statut.ACTIF
        # La réinscription est repoussée à aujourd'hui (nouveau cycle).
        assert m.date_derniere_reinscription == date.today()

    def test_temporaire_activation_initiale_exige_les_3_frais(self):
        """Première activation (TEMPORAIRE) : payer l'adhésion seule ne suffit
        pas — les 3 frais restent requis (CH-2 inchangé)."""
        _fee("ADHESION", "10000")
        m = MemberFactory()
        m.statut = Member.Statut.TEMPORAIRE
        m.save(update_fields=["statut"])
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("30000"), date_ouverture=date.today()
        )
        pay_membership_fee_from_savings(m, "ADHESION")
        m.refresh_from_db()
        assert m.statut == Member.Statut.TEMPORAIRE


class TestTransferClosureFlow:
    def _loan(self, member, solde):
        lr = LoanRequest.objects.create(
            member=member, montant_demande=Decimal("100000"), duree_mois=6,
            motif="x", statut=LoanRequest.Statut.APPROUVEE,
        )
        loan = Loan.objects.create(
            member=member, loan_request=lr, numero_dossier=f"GF-CR-{member.id}",
            montant=Decimal("100000"), taux_interet=Decimal("0.10"), duree_mois=6,
            date_decaissement=date.today(),
            date_premiere_echeance=date.today() + timedelta(days=30),
            montant_total_du=Decimal(solde), solde_restant=Decimal(solde),
            statut=Loan.Statut.ACTIF,
        )
        LoanInstallment.objects.create(
            loan=loan, numero_echeance=1,
            date_echeance=date.today() + timedelta(days=30),
            montant_capital=Decimal(solde), montant_interets=Decimal("0"),
            montant_total=Decimal(solde), statut=LoanInstallment.Statut.A_VENIR,
        )
        return loan

    def test_remboursement_integral_cloture_le_credit(self):
        m = MemberFactory()
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("50000"), date_ouverture=date.today()
        )
        loan = self._loan(m, "40000")

        repay_loan_from_savings(loan, Decimal("40000"))

        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("0.00")
        assert loan.statut == Loan.Statut.CLOTURE
        inst = LoanInstallment.objects.get(loan=loan)
        assert inst.statut == LoanInstallment.Statut.PAYEE

    def test_transfert_apport_gele_solde_le_credit(self):
        # Le membre transfère son apport GELÉ (que le transfert ordinaire ne
        # peut pas ponctionner) pour éteindre son crédit.
        m = MemberFactory()
        classic = ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("10000"), date_ouverture=date.today()
        )
        loan = self._loan(m, "8000")
        # Apport gelé sur la demande (10 000), grisé au retrait.
        loan.loan_request.montant_gele_demandeur = Decimal("10000")
        loan.loan_request.motif_gel_demandeur = "Apport personnel"
        loan.loan_request.save(
            update_fields=["montant_gele_demandeur", "motif_gel_demandeur"]
        )

        repay_loan_from_frozen(loan)  # défaut = tout l'apport, borné au reste dû

        loan.refresh_from_db()
        classic.refresh_from_db()
        assert loan.solde_restant == Decimal("0.00")
        assert loan.statut == Loan.Statut.CLOTURE
        # 8 000 ponctionnés (borné au reste dû) ; le gel restant = 2 000.
        assert classic.solde == Decimal("2000.00")
        loan.loan_request.refresh_from_db()
        assert loan.loan_request.montant_gele_demandeur == Decimal("2000")
