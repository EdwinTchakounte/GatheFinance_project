"""Porte des frais d'étude (2026) — frais d'abord, avaliste ensuite.

Règle : les 5000 XAF de frais d'étude sont exigibles AVANT toute instruction et
avant même que l'avaliste soit sollicité. Trois canaux, un seul au choix :
agence, mobile money, déduction sur épargne classique.

Ces tests verrouillent :
  1. L'ordre : rien ne bouge (et personne n'est dérangé) tant que ce n'est pas
     payé ; l'avaliste n'est sollicité qu'à l'encaissement.
  2. Le canal déduction épargne, et ce qu'il refuse de ponctionner.
  3. La convergence : les trois canaux passent par le même point de sortie.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AppSetting
from apps_coop.loans.models import AvalisteConsent, LoanRequest
from apps_coop.loans.guarantee_tranches import earmark_guarantee_tranches
from apps_coop.loans.study_fee_services import (
    StudyFeeError,
    pay_study_fee_from_savings,
)
from apps_coop.payments.models import FeeType, Payment
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderTranche,
)
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db

FEE = Decimal("5000")


@pytest.fixture(autouse=True)
def _fee_configured():
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais de demande de crédit", "montant": FEE, "actif": True},
    )
    AppSetting.objects.update_or_create(
        cle="lender.tranche.min_amount", defaults={"valeur": "1000"}
    )


def _member(solde=Decimal("0"), *, placements=()):
    m = MemberFactory()
    if solde > 0:
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal(solde), date_ouverture=date.today()
        )
    if placements:
        opt_in_lender(member=m, is_global=False)
        for p in placements:
            add_tranche(member=m, montant=Decimal(p))
    return m


def _pending_request(member, *, avaliste_numero="", avaliste_nom=""):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("50000"),
        duree_mois=3,
        motif="Test porte frais",
        statut=LoanRequest.Statut.EN_ATTENTE,
        avaliste_numero_saisi=avaliste_numero,
        avaliste_nom_saisi=avaliste_nom,
    )


# ---------------------------------------------------------------------------
# 1 — Déduction sur épargne
# ---------------------------------------------------------------------------


class TestDeductionEpargne:
    def test_deduction_debite_et_ouvre_linstruction(self):
        m = _member(solde=Decimal("20000"))
        lr = _pending_request(m)

        payment = pay_study_fee_from_savings(lr)

        assert payment.source == Payment.Source.DEDUCTION_EPARGNE
        assert payment.statut == Payment.Statut.VALIDE, (
            "transfert interne : rien à encaisser, le paiement naît validé"
        )
        assert payment.montant == FEE

        acct = ClassicSavingsAccount.objects.get(member=m)
        assert acct.solde == Decimal("15000")

        lr.refresh_from_db()
        assert lr.frais_demande_credit_paye is True
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION

    def test_deduction_ecrit_au_ledger(self):
        """Traçabilité : le débit doit laisser une écriture typée, pas un
        ajustement muet du solde."""
        m = _member(solde=Decimal("20000"))
        lr = _pending_request(m)

        payment = pay_study_fee_from_savings(lr)

        tx = ClassicSavingsTransaction.objects.get(payment=payment)
        assert tx.type_op == ClassicSavingsTransaction.TypeOp.FRAIS_DEMANDE_CREDIT
        assert tx.montant == FEE
        assert tx.solde_apres == Decimal("15000")

    def test_solde_insuffisant_refuse(self):
        m = _member(solde=Decimal("3000"))
        lr = _pending_request(m)

        with pytest.raises(StudyFeeError, match="insuffisante"):
            pay_study_fee_from_savings(lr)

        assert ClassicSavingsAccount.objects.get(member=m).solde == Decimal("3000")
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE

    def test_le_placement_nest_pas_ponctionnable(self):
        """20k de solde mais tout est placé → 0 retirable, donc pas de frais
        payables sur l'épargne, même si `solde` couvre largement les 5000."""
        m = _member(solde=Decimal("20000"), placements=["20000"])
        lr = _pending_request(m)

        with pytest.raises(StudyFeeError, match="insuffisante"):
            pay_study_fee_from_savings(lr)

    def test_lepargne_gelee_en_garantie_nest_pas_ponctionnable(self):
        """Le collatéral censé couvrir le crédit ne peut pas servir à payer les
        frais d'étude de ce même crédit."""
        m = _member(solde=Decimal("20000"))
        lr_gel = _pending_request(m)
        lr_gel.montant_gele_demandeur = Decimal("18000")
        lr_gel.save(update_fields=["montant_gele_demandeur"])
        # 20000 − 18000 gelés = 2000 retirables < 5000
        with pytest.raises(StudyFeeError, match="insuffisante"):
            pay_study_fee_from_savings(lr_gel)

    def test_sans_compte_classique_refuse_avec_alternative(self):
        m = _member()
        lr = _pending_request(m)

        with pytest.raises(StudyFeeError, match="agence"):
            pay_study_fee_from_savings(lr)

    def test_double_paiement_refuse(self):
        m = _member(solde=Decimal("20000"))
        lr = _pending_request(m)
        pay_study_fee_from_savings(lr)

        lr.refresh_from_db()
        with pytest.raises(StudyFeeError):
            pay_study_fee_from_savings(lr)

        assert ClassicSavingsAccount.objects.get(member=m).solde == Decimal("15000")


# ---------------------------------------------------------------------------
# 2 — Frais d'abord, avaliste ensuite
# ---------------------------------------------------------------------------


class TestOrdreFraisAvaliste:
    def test_lavaliste_nest_pas_sollicite_avant_paiement(self):
        """Le cœur de la règle : tant que les frais ne sont pas payés, aucun
        tiers n'est dérangé — pas de consentement, donc pas de notification."""
        avaliste = _member(solde=Decimal("100000"))
        borrower = _member(solde=Decimal("20000"))
        lr = _pending_request(
            borrower,
            avaliste_numero=avaliste.numero_membre,
            avaliste_nom=avaliste.nom,
        )

        assert not AvalisteConsent.objects.filter(loan_request=lr).exists()
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE

    def test_le_paiement_sollicite_lavaliste(self):
        avaliste = _member(solde=Decimal("100000"))
        borrower = _member(solde=Decimal("20000"))
        lr = _pending_request(
            borrower,
            avaliste_numero=avaliste.numero_membre,
            avaliste_nom=avaliste.nom,
        )

        pay_study_fee_from_savings(lr)

        lr.refresh_from_db()
        assert lr.frais_demande_credit_paye is True
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE_AVALISTE, (
            "l'avaliste doit être sollicité à l'encaissement, pas avant"
        )
        consent = AvalisteConsent.objects.get(loan_request=lr)
        assert consent.avaliste_id == avaliste.id
        assert consent.statut == AvalisteConsent.Statut.PENDING
        # La désignation en attente est consommée.
        assert lr.avaliste_numero_saisi == ""

    def test_avaliste_devenu_invalide_ne_perd_pas_les_frais(self):
        """Fenêtre soumission → paiement : si l'avaliste n'est plus valable, on
        n'annule pas des frais déjà encaissés dans un hook de paiement. La
        demande reste en attente d'une nouvelle désignation, avec un motif."""
        avaliste = _member(solde=Decimal("100000"))
        borrower = _member(solde=Decimal("20000"))
        lr = _pending_request(
            borrower,
            avaliste_numero=avaliste.numero_membre,
            avaliste_nom=avaliste.nom,
        )
        # L'avaliste vide son épargne entre-temps → couverture insuffisante.
        acct = ClassicSavingsAccount.objects.get(member=avaliste)
        acct.solde = Decimal("0")
        acct.save(update_fields=["solde"])

        pay_study_fee_from_savings(lr)

        lr.refresh_from_db()
        assert lr.frais_demande_credit_paye is True, "les frais restent encaissés"
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE
        assert "avaliste" in lr.motif_rejet.lower()
        assert not AvalisteConsent.objects.filter(loan_request=lr).exists()


# ---------------------------------------------------------------------------
# 3 — Convergence des canaux
# ---------------------------------------------------------------------------


class TestConvergenceDesCanaux:
    def test_le_canal_agence_passe_par_le_meme_point(self):
        """Le cash-in admin doit solliciter l'avaliste exactement comme la
        déduction épargne — sinon le parcours dépend du canal choisi."""
        from apps_coop.payments.services import _hook_loan_request_fees

        avaliste = _member(solde=Decimal("100000"))
        borrower = _member(solde=Decimal("20000"))
        lr = _pending_request(
            borrower,
            avaliste_numero=avaliste.numero_membre,
            avaliste_nom=avaliste.nom,
        )
        payment = Payment.objects.create(
            member=borrower,
            montant=FEE,
            type=Payment.Type.FRAIS_DEMANDE_CREDIT,
            source=Payment.Source.MANUEL,
            statut=Payment.Statut.VALIDE,
            date_versement=timezone.now(),
            date_validation=timezone.now(),
        )

        _hook_loan_request_fees(payment, {})

        lr.refresh_from_db()
        assert lr.frais_demande_credit_paye is True
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE_AVALISTE
        assert AvalisteConsent.objects.filter(loan_request=lr).exists()

    def test_sans_avaliste_le_paiement_ouvre_directement_linstruction(self):
        from apps_coop.payments.services import _hook_loan_request_fees

        borrower = _member(solde=Decimal("20000"))
        lr = _pending_request(borrower)
        payment = Payment.objects.create(
            member=borrower,
            montant=FEE,
            type=Payment.Type.FRAIS_DEMANDE_CREDIT,
            source=Payment.Source.MANUEL,
            statut=Payment.Statut.VALIDE,
            date_versement=timezone.now(),
            date_validation=timezone.now(),
        )

        _hook_loan_request_fees(payment, {})

        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION
