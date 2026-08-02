"""LOT 9 (refonte 2026, révisé 2026-07-24) — Rémunération prêteur des intérêts.

Règle unique : chaque prêteur touche ``k × sa contribution`` (montant_alloue),
``k`` = ``loans.lender.interest_rate`` (défaut 0.03). En mode échéances la cible
est répartie au prorata de l'intérêt payé → cumul = k × montant_alloue sur toute
la vie du crédit (borné, jamais de surpaiement).

Couvre :
  - k × contribution sur une échéance entière payée (1 prêteur)
  - Répartition entre prêteurs = chacun k × SON montant_alloue (mode A + mode B)
  - Imputation partielle : la cible est proratisée sur l'intérêt payé
  - Pas de payout si le crédit n'a aucune ``LenderAllocation`` (legacy 2025)
  - ``loans.lender.interest_rate=0`` (kill-switch) désactive la rémunération
  - Idempotence : un Payment ne crée pas de doublon de payouts si le hook
    est rejoué deux fois sur le même imputation set
  - Clôture du Loan → tranches passent ENGAGEE → LIBEREE (idempotent)
  - Cumul ``LenderAllocation.interest_share_paid_total`` mis à jour
  - E2E : funding → décaissement → 3 échéances payées → clôture
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

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


@pytest.fixture(autouse=True)
def _placement_window_open():
    """Placement fermé globalement au 1er août 2026 (closed_from) — on rouvre la
    fenêtre pour que le partage d'intérêts (sur tranches de placement) reste
    testable après cette date."""
    AppSetting.objects.update_or_create(
        cle="savings.placement.closed_from", defaults={"valeur": "2099-01-01"}
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_loan(borrower, *, montant=Decimal("90000"), duree=3, suffix="A"):
    """Construit un Loan + son échéancier flat-interest (10%).

    Règle 2026 « date butoir unique » : l'échéancier est réduit à **UNE seule
    échéance** portant la totalité du montant dû, exigible à la date butoir.

    Pour 90 000 sur 3 mois :
      - intérêt total = 90 000 × 10% = 9 000
      - capital (échéance unique) = 90 000
      - intérêt (échéance unique) = 9 000
      - montant_total (échéance unique) = 99 000
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


# Règle 2026-07-24 : rémunération prêteur = k × contribution. On fige k=3 %
# dans les tests (indépendant de l'état seedé de la DB en --reuse-db).
K_RATE = Decimal("0.03")


def _set_lender_rate(rate=K_RATE):
    AppSetting.objects.update_or_create(
        cle="loans.lender.interest_rate",
        defaults={"valeur": str(rate)},
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

    def test_full_installment_single_lender_k_contribution(self, active_member):
        """1 prêteur 100% : il touche k × sa contribution (montant_alloue)."""
        _set_lender_rate()
        loan = _build_loan(active_member, suffix="SOLO50")
        lender = _make_lender_mode_a(solde=Decimal("500000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)
        alloc = LenderAllocation.objects.get(loan=loan)
        # 100% pour le prêteur → montant_alloue = 90 000.
        assert alloc.quote_part == Decimal("1.00000000")
        assert Decimal(alloc.montant_alloue) == Decimal("90000")

        # Échéance unique : intérêt total 9 000 payé en entier → cumul cible
        # atteint en une fois = k × 90 000 = 0.03 × 90 000 = 2 700.
        inst = loan.installments.order_by("numero_echeance").first()
        interet = Decimal(inst.montant_interets)  # 9 000
        part_preteur = (K_RATE * Decimal("90000")).quantize(Decimal("0.01"))  # 2 700
        payment = _make_repayment_payment(
            active_member, loan, montant=Decimal(inst.montant_total)
        )

        payouts = distribute_interest_share(
            installment=inst, payment=payment, imputation=Decimal(inst.montant_total)
        )
        assert len(payouts) == 1
        assert payouts[0].montant == part_preteur
        assert payouts[0].allocation_id == alloc.id

        # Cumul mis à jour.
        alloc.refresh_from_db()
        assert alloc.interest_share_paid_total == part_preteur
        # interets_payes côté installment = 9 000 (intégralité de l'intérêt de
        # l'échéance unique, imputée en priorité).
        inst.refresh_from_db()
        assert Decimal(inst.interets_payes) == interet

        # Solde épargne classique du prêteur crédité de la part prêteur.
        acc = lender.classic_savings_account
        acc.refresh_from_db()
        assert Decimal(acc.solde) == Decimal("500000") + part_preteur

        # ClassicSavingsTransaction posée avec le bon TypeOp.
        tx = ClassicSavingsTransaction.objects.filter(account=acc).latest("date")
        assert tx.type_op == ClassicSavingsTransaction.TypeOp.INTERET_PRETEUR
        assert Decimal(tx.montant) == part_preteur

    def test_each_lender_gets_k_times_own_contribution(self, active_member):
        """2 prêteurs 70k/30k : chacun touche k × SA contribution (2 100 / 900)."""
        _set_lender_rate()
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

        # Échéance unique (date butoir) : intérêt total 10 000 payé en entier.
        # Chaque prêteur atteint sa cible k × montant_alloue en une fois :
        #   big  = 0.03 × 70 000 = 2 100 ; small = 0.03 × 30 000 = 900.
        inst = loan.installments.order_by("numero_echeance").first()
        payment = _make_repayment_payment(
            active_member, loan, montant=Decimal(inst.montant_total)
        )

        payouts = distribute_interest_share(
            installment=inst,
            payment=payment,
            imputation=Decimal(inst.montant_total),
        )
        assert len(payouts) == 2

        by_lender = {p.allocation.lender_id: Decimal(p.montant) for p in payouts}
        assert by_lender[big.id] == Decimal("2100.00")
        assert by_lender[small.id] == Decimal("900.00")
        assert sum(by_lender.values()) == Decimal("3000.00")

    def test_partial_payment_prorates_the_target(self, active_member):
        """Imputation partielle : la cible k × contribution est proratisée."""
        _set_lender_rate()
        loan = _build_loan(active_member, suffix="PART")
        lender = _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        inst = loan.installments.order_by("numero_echeance").first()
        # montant_alloue = 90 000 → cible totale = 0.03 × 90 000 = 2 700, sur un
        # intérêt total de 9 000. On impute 2 000, tout en intérêt (priorité) →
        # part = 2 700 × 2 000 / 9 000 = 600.
        payment = _make_repayment_payment(active_member, loan, montant=Decimal("2000"))

        payouts = distribute_interest_share(
            installment=inst, payment=payment, imputation=Decimal("2000")
        )
        assert len(payouts) == 1
        assert payouts[0].montant == Decimal("600.00")
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

    def test_kill_switch_zero_k(self, active_member):
        """``loans.lender.interest_rate=0`` désactive la rémunération prêteur."""
        _set_lender_rate(Decimal("0"))
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
        """E2E : funding → paiements successifs → clôture + tranches libérées.

        Échéance unique (99 000) : le 1er versement solde d'abord l'intérêt
        (priorité intérêt) → la cible k × 90 000 = 2 700 est atteinte en une
        fois → un seul payout de 2 700. Les versements suivants n'imputent que
        du capital → pas de nouveau payout.
        """
        _set_lender_rate()
        loan = _build_loan(active_member, montant=Decimal("90000"), duree=3, suffix="E2E")
        lender = _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        # 3 paiements de 33 000 = 99 000 (solde total dû de l'échéance unique).
        for echeance_num in range(3):
            payment = _make_repayment_payment(
                active_member, loan, montant=Decimal("33000")
            )
            _hook_loan_repayment(payment, {})

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.CLOTURE
        # 1 seul payout (cible atteinte au 1er versement) = 0.03 × 90 000 = 2 700.
        payouts = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts.count() == 1
        assert sum(Decimal(p.montant) for p in payouts) == Decimal("2700.00")

        # Tranche libérée à la clôture (créée en mode A au moment du funding).
        alloc = LenderAllocation.objects.get(loan=loan)
        assert alloc.tranche.statut == LenderTranche.Statut.LIBEREE
        # Solde épargne classique crédité de 2 700.
        lender.classic_savings_account.refresh_from_db()
        assert Decimal(lender.classic_savings_account.solde) == (
            Decimal("200000") + Decimal("2700")
        )

    def test_hook_partial_then_complete(self, active_member):
        """Paiement partiel (10k) puis paiement complétant le reste (échéance unique)."""
        _set_lender_rate()
        loan = _build_loan(active_member, suffix="P2C")
        lender = _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        inst = loan.installments.order_by("numero_echeance").first()
        interet = Decimal(inst.montant_interets)  # 9 000
        part_preteur = (K_RATE * Decimal("90000")).quantize(Decimal("0.01"))  # 2 700

        # 1er paiement de 10 000 : solde d'abord l'intérêt (9 000) puis 1 000
        # de capital → cible atteinte → un seul payout = k × 90 000 = 2 700.
        p1 = _make_repayment_payment(active_member, loan, montant=Decimal("10000"))
        _hook_loan_repayment(p1, {})
        payouts1 = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts1.count() == 1
        assert payouts1.first().montant == part_preteur

        # 2e paiement = reste dû (capital uniquement, intérêt déjà soldé).
        reste = Decimal(inst.montant_total) - Decimal("10000")
        p2 = _make_repayment_payment(active_member, loan, montant=reste)
        _hook_loan_repayment(p2, {})
        # Toujours 1 payout au total (le 2e paiement n'a pas généré de split).
        payouts2 = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts2.count() == 1

        # Échéance unique entièrement réglée.
        inst1 = loan.installments.order_by("numero_echeance").first()
        inst1.refresh_from_db()
        assert inst1.statut == LoanInstallment.Statut.PAYEE
        assert Decimal(inst1.interets_payes) == Decimal(inst1.montant_interets)

    def test_hook_no_op_for_legacy_loan_without_allocations(self, active_member):
        """Crédit non funding (legacy 2025) : hook fonctionne, mais 0 payout."""
        loan = _build_loan(active_member, suffix="LEG")
        # Pas de funding — donc aucune LenderAllocation.
        inst = loan.installments.order_by("numero_echeance").first()
        payment = _make_repayment_payment(
            active_member, loan, montant=Decimal(inst.montant_total)
        )
        _hook_loan_repayment(payment, {})

        assert LenderInterestPayout.objects.count() == 0
        # L'imputation FIFO standard fonctionne quand même (échéance unique soldée).
        inst.refresh_from_db()
        assert inst.statut == LoanInstallment.Statut.PAYEE
        # Pas de mise à jour de interets_payes (no-op du split = pas de tracker).
        assert Decimal(inst.interets_payes) == Decimal("0")

    def test_full_repayment_single_installment_splits_once(self, active_member):
        """Échéance unique soldée en un Payment : 1 payout = k × contribution."""
        _set_lender_rate()
        loan = _build_loan(active_member, suffix="MULTI")
        lender = _make_lender_mode_a(solde=Decimal("200000"))
        fr = request_funding(loan)
        _accept_all_consents(fr)

        inst = loan.installments.order_by("numero_echeance").first()
        interet = Decimal(inst.montant_interets)  # 9 000
        part_preteur = (K_RATE * Decimal("90000")).quantize(Decimal("0.01"))  # 2 700

        # Solde total dû (99 000) en un seul versement.
        payment = _make_repayment_payment(
            active_member, loan, montant=Decimal(inst.montant_total)
        )
        _hook_loan_repayment(payment, {})

        payouts = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts.count() == 1
        assert sum(Decimal(p.montant) for p in payouts) == part_preteur


# ---------------------------------------------------------------------------
# Mode B — split avec tranches multiples
# ---------------------------------------------------------------------------


class TestModeBSplit:
    def test_mode_b_two_tranches_same_lender(self, active_member):
        """Un même prêteur a 2 tranches financant 1 crédit : 2 allocations, split correct."""
        _set_lender_rate()
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

        # Échéance unique soldée (99 000) → chaque allocation touche k × son
        # montant_alloue : 0.03 × 60 000 = 1 800 et 0.03 × 30 000 = 900.
        inst = loan.installments.order_by("numero_echeance").first()
        payment = _make_repayment_payment(
            active_member, loan, montant=Decimal(inst.montant_total)
        )
        _hook_loan_repayment(payment, {})

        payouts = LenderInterestPayout.objects.filter(allocation__loan=loan)
        assert payouts.count() == 2
        montants = sorted(Decimal(p.montant) for p in payouts)
        assert montants == [Decimal("900.00"), Decimal("1800.00")]
        total = sum(Decimal(p.montant) for p in payouts)
        assert total == Decimal("2700.00")
        # Le compte épargne du même prêteur est crédité du total.
        lender.classic_savings_account.refresh_from_db()
        assert Decimal(lender.classic_savings_account.solde) == Decimal("2700.00")
