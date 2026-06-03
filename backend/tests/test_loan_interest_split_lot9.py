"""LOT 9 (refonte 2026) — Partage 50/50 des intérêts crédit (§7.5).

Couvre :
  - Split 50/50 sur une échéance entière payée (1 prêteur)
  - Split au prorata des ``quote_part`` sur plusieurs prêteurs (mode A + mode B)
  - Imputation partielle : seule la portion **intérêt** alimente le split
  - Pas de split si le crédit n'a aucune ``LenderAllocation`` (legacy 2025)
  - ``lender.interest_share_rate=0`` (kill-switch) désactive le split
  - Idempotence : un Payment ne crée pas de doublon de payouts si le hook
    est rejoué deux fois sur le même imputation set
  - Clôture du Loan → tranches passent ENGAGEE → LIBEREE (idempotent)
  - Cumul ``LenderAllocation.interest_share_paid_total`` mis à jour
  - E2E : funding → décaissement → 3 échéances payées → clôture
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import pytest
from django.utils import timezone

from apps_coop.audit.models import AppSetting
from apps_coop.loans.funding_services import request_funding, respond_to_consent_request
from apps_coop.loans.lender_payouts import (
    distribute_interest_share,
    release_loan_tranches,
)
from apps_coop.loans.models import (
    LenderAllocation,
    LenderInterestPayout,
    Loan,
    LoanInstallment,
    LoanRepayment,
    LoanRequest,
)
from apps_coop.loans.services import generate_installments_flat_interest
from apps_coop.payments.models import Payment
from apps_coop.payments.services import _hook_loan_repayment
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderTranche,
)
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _override_media_root(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_loan(borrower, *, montant=Decimal("90000"), duree=3, suffix="A"):
    """Construit un Loan + ses 3 échéances flat-interest (10%).

    Pour 90 000 sur 3 mois :
      - intérêt total = 90 000 × 10% = 9 000
      - capital/échéance = 30 000
      - intérêt/échéance = 3 000
      - montant_total/échéance = 33 000
    """
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=montant,
        duree_mois=duree,
        motif="Test split intérêts",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    loan = Loan.objects.create(
        member=borrower,
        loan_request=lr,
        numero_dossier=f"GF-CR-{suffix}",
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


def _make_lender_mode_a(*, solde):
    lender = MemberFactory()
    ClassicSavingsAccount.objects.create(
        member=lender,
        solde=solde,
        date_ouverture=date.today(),
    )
    opt_in_lender(member=lender, is_global=True)
    return lender


def _make_lender_mode_b(*, tranches):
    AppSetting.objects.update_or_create(
        cle="lender.tranche.min_amount",
        defaults={"valeur": "1000"},
    )
    lender = MemberFactory()
    opt_in_lender(member=lender, is_global=False)
    for montant in tranches:
        add_tranche(member=lender, montant=Decimal(montant))
    return lender


def _accept_all_consents(funding_request):
    """Helper E2E : accepte tous les consent_requests d'une vague."""
    for cr in funding_request.consent_requests.filter(statut="pending"):
        respond_to_consent_request(consent_request=cr, accept=True)


def _make_repayment_payment(member, loan, *, montant):
    return Payment.objects.create(
        member=member,
        montant=montant,
        type=Payment.Type.REMBOURSEMENT,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        loan=loan,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
    )


# ---------------------------------------------------------------------------
# distribute_interest_share — unitaire
# ---------------------------------------------------------------------------


class TestDistributeInterestShare:
    def test_no_split_when_no_allocation(self, active_member):
        """Crédit legacy sans LenderAllocation : aucun payout."""
        loan = _build_loan(active_member, suffix="NOALLOC")
        inst = loan.installments.order_by("numero_echeance").first()
        payment = _make_repayment_payment(active_member, loan, montant=Decimal("33000"))

        payouts = distribute_interest_share(
            installment=inst, payment=payment, imputation=Decimal("33000")
        )
        assert payouts == []
        # ``interets_payes`` reste à zéro côté installment (aucun mouvement).
        inst.refresh_from_db()
        assert Decimal(inst.interets_payes) == Decimal("0")
        assert LenderInterestPayout.objects.count() == 0

    def test_full_installment_single_lender_split_50_50(self, active_member):
        """1 prêteur 100% : 50% des intérêts vont au prêteur, 50% à la coop."""
        loan = _build_loan(active_member, suffix="SOLO50")
        lender = _make_lender_mode_a(solde=Decimal("500000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)
        alloc = LenderAllocation.objects.get(loan=loan)
        # 100% pour le prêteur.
        assert alloc.quote_part == Decimal("1.00000000")

        inst = loan.installments.order_by("numero_echeance").first()
        # intérêt de cette échéance : 3 000 ; split 50/50 → 1 500 prêteur.
        payment = _make_repayment_payment(active_member, loan, montant=Decimal("33000"))

        payouts = distribute_interest_share(
            installment=inst, payment=payment, imputation=Decimal("33000")
        )
        assert len(payouts) == 1
        assert payouts[0].montant == Decimal("1500.00")
        assert payouts[0].allocation_id == alloc.id

        # Cumul mis à jour.
        alloc.refresh_from_db()
        assert alloc.interest_share_paid_total == Decimal("1500.00")
        # interets_payes côté installment = 3 000 (l'intégralité de l'intérêt
        # de l'échéance vient d'être imputée).
        inst.refresh_from_db()
        assert Decimal(inst.interets_payes) == Decimal("3000.00")

        # Solde épargne classique du prêteur crédité de 1 500.
        acc = lender.classic_savings_account
        acc.refresh_from_db()
        assert Decimal(acc.solde) == Decimal("500000") + Decimal("1500")

        # ClassicSavingsTransaction posée avec le bon TypeOp.
        tx = ClassicSavingsTransaction.objects.filter(account=acc).latest("date")
        assert tx.type_op == ClassicSavingsTransaction.TypeOp.INTERET_PRETEUR
        assert Decimal(tx.montant) == Decimal("1500.00")

    def test_split_proportional_to_quote_parts(self, active_member):
        """2 prêteurs avec quote_parts différentes : split au prorata."""
        loan = _build_loan(active_member, montant=Decimal("100000"), suffix="PRORATA")
        # Force allocation à 70/30 via mode A : 2 prêteurs disponibles avec
        # capacités 70k et 30k → first_fit donne (70k, 30k).
        big = _make_lender_mode_a(solde=Decimal("70000"))
        small = _make_lender_mode_a(solde=Decimal("30000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        allocs = list(LenderAllocation.objects.filter(loan=loan).order_by("-montant_alloue"))
        assert len(allocs) == 2
        assert allocs[0].montant_alloue == Decimal("70000")
        assert allocs[0].lender_id == big.id
        assert allocs[1].montant_alloue == Decimal("30000")
        assert allocs[1].lender_id == small.id

        # 1ère échéance : intérêt = 100 000 × 10% / 3 = 3 333.33...
        # Le générateur arrondit donc on lit l'échéance.
        inst = loan.installments.order_by("numero_echeance").first()
        interet_ech = Decimal(inst.montant_interets)
        payment = _make_repayment_payment(
            active_member, loan, montant=Decimal(inst.montant_total)
        )

        payouts = distribute_interest_share(
            installment=inst,
            payment=payment,
            imputation=Decimal(inst.montant_total),
        )
        assert len(payouts) == 2

        total_pretteurs = sum(Decimal(p.montant) for p in payouts)
        # Total = intérêt_échéance × 0.5, arrondi 2 décimales ROUND_HALF_UP
        # (même règle d'arrondi que ``lender_payouts._q``).
        expected = (interet_ech * Decimal("0.5")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert total_pretteurs == expected

        # Big prend ~70%, small ~30%, avec absorption du résidu par la dernière.
        by_lender = {p.allocation.lender_id: p.montant for p in payouts}
        assert by_lender[big.id] > by_lender[small.id]

    def test_partial_payment_only_interest_portion_splits(self, active_member):
        """Imputation partielle : seule la portion intérêt (priorité intérêt) split."""
        loan = _build_loan(active_member, suffix="PART")
        lender = _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        inst = loan.installments.order_by("numero_echeance").first()
        # Échéance : capital 30k + intérêt 3k = 33k. On impute juste 2 000 :
        # tout en intérêt → split (1 000 prêteur, 1 000 coop).
        payment = _make_repayment_payment(active_member, loan, montant=Decimal("2000"))

        payouts = distribute_interest_share(
            installment=inst, payment=payment, imputation=Decimal("2000")
        )
        assert len(payouts) == 1
        assert payouts[0].montant == Decimal("1000.00")
        inst.refresh_from_db()
        assert Decimal(inst.interets_payes) == Decimal("2000.00")

    def test_imputation_after_interest_already_paid_no_split(self, active_member):
        """Si l'intérêt de l'échéance est déjà soldé, le surplus va au capital."""
        loan = _build_loan(active_member, suffix="POSTINT")
        _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        inst = loan.installments.order_by("numero_echeance").first()
        # Simule : intérêt déjà entièrement payé sur cette échéance.
        inst.interets_payes = inst.montant_interets
        inst.save(update_fields=["interets_payes"])

        payment = _make_repayment_payment(active_member, loan, montant=Decimal("10000"))
        payouts = distribute_interest_share(
            installment=inst, payment=payment, imputation=Decimal("10000")
        )
        assert payouts == []

    def test_kill_switch_zero_rate(self, active_member):
        """``lender.interest_share_rate=0`` désactive complètement le split."""
        AppSetting.objects.update_or_create(
            cle="lender.interest_share_rate",
            defaults={"valeur": "0"},
        )
        loan = _build_loan(active_member, suffix="KILL")
        _make_lender_mode_a(solde=Decimal("500000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)
        inst = loan.installments.order_by("numero_echeance").first()
        payment = _make_repayment_payment(active_member, loan, montant=Decimal("33000"))
        payouts = distribute_interest_share(
            installment=inst, payment=payment, imputation=Decimal("33000")
        )
        assert payouts == []
        # interets_payes reste à 0 — pas d'effet de bord côté tracker.
        inst.refresh_from_db()
        assert Decimal(inst.interets_payes) == Decimal("0")


# ---------------------------------------------------------------------------
# release_loan_tranches — libération à la clôture
# ---------------------------------------------------------------------------


class TestReleaseTranches:
    def test_release_engaged_tranches(self, active_member):
        loan = _build_loan(active_member, suffix="REL1")
        lender = _make_lender_mode_b(tranches=[Decimal("90000")])
        fr = request_funding(loan)
        _accept_all_consents(fr)
        # Tranche → ENGAGEE après funding.
        tranche = LenderTranche.objects.get(member=lender)
        assert tranche.statut == LenderTranche.Statut.ENGAGEE

        count = release_loan_tranches(loan)
        assert count == 1
        tranche.refresh_from_db()
        assert tranche.statut == LenderTranche.Statut.LIBEREE
        assert tranche.released_at is not None

    def test_release_idempotent_when_already_released(self, active_member):
        loan = _build_loan(active_member, suffix="REL2")
        _make_lender_mode_b(tranches=[Decimal("90000")])
        fr = request_funding(loan)
        _accept_all_consents(fr)
        release_loan_tranches(loan)
        # Deuxième appel : no-op.
        count2 = release_loan_tranches(loan)
        assert count2 == 0

    def test_release_skips_when_no_engaged_tranches(self, active_member):
        """Crédit sans tranches engagées (legacy 2025) : no-op."""
        loan = _build_loan(active_member, suffix="REL3")
        count = release_loan_tranches(loan)
        assert count == 0


# ---------------------------------------------------------------------------
# Hook complet — _hook_loan_repayment + split + clôture
# ---------------------------------------------------------------------------


class TestHookIntegration:
    def test_full_repayment_cycle_triggers_split_and_closes(self, active_member):
        """E2E : funding → 3 paiements pleins → clôture + tranches libérées."""
        loan = _build_loan(active_member, montant=Decimal("90000"), duree=3, suffix="E2E")
        lender = _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        # 3 paiements de 33 000 (capital 30k + intérêt 3k chacun).
        for echeance_num in range(3):
            payment = _make_repayment_payment(
                active_member, loan, montant=Decimal("33000")
            )
            _hook_loan_repayment(payment, {})

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.CLOTURE
        # 3 payouts (1 par échéance), chacun = 3 000 × 0.5 = 1 500.
        payouts = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts.count() == 3
        assert sum(Decimal(p.montant) for p in payouts) == Decimal("4500.00")

        # Tranche libérée à la clôture (créée en mode A au moment du funding).
        alloc = LenderAllocation.objects.get(loan=loan)
        assert alloc.tranche.statut == LenderTranche.Statut.LIBEREE
        # Solde épargne classique crédité de 1 500 × 3.
        lender.classic_savings_account.refresh_from_db()
        assert Decimal(lender.classic_savings_account.solde) == (
            Decimal("200000") + Decimal("4500")
        )

    def test_hook_partial_then_complete(self, active_member):
        """Paiement partiel (10k) puis paiement complétant (23k) sur 1 échéance."""
        loan = _build_loan(active_member, suffix="P2C")
        lender = _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        # 1er paiement de 10 000 (couvre 3 000 intérêt + 7 000 capital).
        p1 = _make_repayment_payment(active_member, loan, montant=Decimal("10000"))
        _hook_loan_repayment(p1, {})
        # 1 payout = 3 000 × 0.5 = 1 500.
        payouts1 = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts1.count() == 1
        assert payouts1.first().montant == Decimal("1500.00")

        # 2e paiement de 23 000 (capital restant uniquement, intérêt déjà soldé).
        p2 = _make_repayment_payment(active_member, loan, montant=Decimal("23000"))
        _hook_loan_repayment(p2, {})
        # Toujours 1 payout au total (le 2e paiement n'a pas généré de split).
        payouts2 = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts2.count() == 1

        # Échéance 1 entièrement réglée.
        inst1 = loan.installments.order_by("numero_echeance").first()
        inst1.refresh_from_db()
        assert inst1.statut == LoanInstallment.Statut.PAYEE
        assert Decimal(inst1.interets_payes) == Decimal(inst1.montant_interets)

    def test_hook_no_op_for_legacy_loan_without_allocations(self, active_member):
        """Crédit non funding (legacy 2025) : hook fonctionne, mais 0 payout."""
        loan = _build_loan(active_member, suffix="LEG")
        # Pas de funding — donc aucune LenderAllocation.
        payment = _make_repayment_payment(active_member, loan, montant=Decimal("33000"))
        _hook_loan_repayment(payment, {})

        assert LenderInterestPayout.objects.count() == 0
        # L'imputation FIFO standard fonctionne quand même.
        inst = loan.installments.order_by("numero_echeance").first()
        inst.refresh_from_db()
        assert inst.statut == LoanInstallment.Statut.PAYEE
        # Pas de mise à jour de interets_payes (no-op du split = pas de tracker).
        assert Decimal(inst.interets_payes) == Decimal("0")

    def test_repayment_across_multiple_installments_splits_per_installment(
        self, active_member
    ):
        """Un seul Payment qui couvre 2 échéances : 2 payouts générés."""
        loan = _build_loan(active_member, suffix="MULTI")
        lender = _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        # 66 000 = 2 échéances entières (33 000 × 2).
        payment = _make_repayment_payment(active_member, loan, montant=Decimal("66000"))
        _hook_loan_repayment(payment, {})

        payouts = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts.count() == 2
        # 2 × 1 500 = 3 000 versés au prêteur.
        assert sum(Decimal(p.montant) for p in payouts) == Decimal("3000.00")


# ---------------------------------------------------------------------------
# Mode B — split avec tranches multiples
# ---------------------------------------------------------------------------


class TestModeBSplit:
    def test_mode_b_two_tranches_same_lender(self, active_member):
        """Un même prêteur a 2 tranches financant 1 crédit : 2 allocations, split correct."""
        loan = _build_loan(active_member, montant=Decimal("90000"), suffix="MB")
        lender = _make_lender_mode_b(tranches=[Decimal("60000"), Decimal("30000")])
        fr = request_funding(loan)
        _accept_all_consents(fr)

        allocs = LenderAllocation.objects.filter(loan=loan)
        assert allocs.count() == 2
        # 60% + 30% = 90% pour ce prêteur ? Non — 60 + 30 = 90 ; total
        # crédit = 90 000 → quote_parts 60k/90k et 30k/90k.
        quote_parts = sorted(Decimal(a.quote_part) for a in allocs)
        assert quote_parts == [
            (Decimal("30000") / Decimal("90000")).quantize(Decimal("0.00000001")),
            (Decimal("60000") / Decimal("90000")).quantize(Decimal("0.00000001")),
        ]

        # 1 paiement plein 33 000 → 3 000 intérêt → split prêteur 1 500
        # réparti entre les 2 allocations au prorata.
        payment = _make_repayment_payment(active_member, loan, montant=Decimal("33000"))
        _hook_loan_repayment(payment, {})

        payouts = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts.count() == 2
        total = sum(Decimal(p.montant) for p in payouts)
        assert total == Decimal("1500.00")
        # Le compte épargne du même prêteur est crédité du total.
        lender.classic_savings_account.refresh_from_db()
        assert Decimal(lender.classic_savings_account.solde) == Decimal("1500.00")
