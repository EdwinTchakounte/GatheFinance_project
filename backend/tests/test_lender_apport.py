"""Apport coop — restitution anticipée d'un placement prêteur (2026-07).

Vérifie : (1) une tranche ENGAGÉE est restituée (capital libéré + intérêts
placement crédités, crédit non soldé reste ACTIF), (2) le prêteur restitué est
EXCLU de la part d'intérêts des remboursements futurs (la coop garde sa part).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.loans.apport_services import ApportError, restitute_tranche_by_apport
from apps_coop.loans.lender_payouts import distribute_interest_share
from apps_coop.loans.models import LenderAllocation, Loan
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderTranche,
)
from apps_coop.loans.funding_services import request_funding
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from tests.factories import MemberFactory
from tests.test_loan_interest_split_lot9 import (
    _accept_all_consents,
    _build_loan,
    _make_repayment_payment,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)


def _lender_with_tranche(montant: str) -> "Member":  # noqa: F821
    lender = MemberFactory()
    ClassicSavingsAccount.objects.create(
        member=lender, solde=Decimal(montant), date_ouverture=date.today()
    )
    opt_in_lender(member=lender, is_global=False)
    add_tranche(member=lender, montant=Decimal(montant))
    return lender


class TestApport:
    def test_restitution_releases_and_credits_interest(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("100000"), suffix="APPORT")
        big = _lender_with_tranche("70000")
        small = _lender_with_tranche("30000")
        fr = request_funding(loan)
        _accept_all_consents(fr)

        # Tranche du gros prêteur, engagée sur ce crédit.
        alloc_big = LenderAllocation.objects.get(loan=loan, lender=big)
        tranche = alloc_big.tranche
        assert tranche is not None
        assert tranche.statut == LenderTranche.Statut.ENGAGEE
        # Antidate pour un prorata d'intérêts > 0.
        LenderTranche.objects.filter(pk=tranche.pk).update(
            created_at=timezone.now() - timedelta(days=60)
        )

        acc_before = ClassicSavingsAccount.objects.get(member=big).solde
        res = restitute_tranche_by_apport(tranche.pk, admin_user=None)

        tranche.refresh_from_db()
        alloc_big.refresh_from_db()
        loan.refresh_from_db()
        assert tranche.statut == LenderTranche.Statut.LIBEREE
        assert alloc_big.restitue_par_apport is True
        assert loan.statut == Loan.Statut.ACTIF  # crédit non soldé, coop reprend
        # Intérêts placement crédités.
        assert Decimal(res["interet_placement"]) > 0
        assert ClassicSavingsAccount.objects.get(member=big).solde > acc_before
        assert ClassicSavingsTransaction.objects.filter(
            account__member=big,
            type_op=ClassicSavingsTransaction.TypeOp.INTERET_PLACEMENT,
        ).exists()

    def test_restituted_lender_excluded_from_future_interest(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("100000"), suffix="EXCL")
        big = _lender_with_tranche("70000")
        small = _lender_with_tranche("30000")
        fr = request_funding(loan)
        _accept_all_consents(fr)

        tranche_big = LenderAllocation.objects.get(loan=loan, lender=big).tranche
        restitute_tranche_by_apport(tranche_big.pk, admin_user=None)

        inst = loan.installments.order_by("numero_echeance").first()
        payment = _make_repayment_payment(
            active_member, loan, montant=Decimal(inst.montant_total)
        )
        payouts = distribute_interest_share(
            installment=inst, payment=payment, imputation=Decimal(inst.montant_total)
        )
        # Seul le petit prêteur (non restitué) touche des intérêts ; la coop garde
        # la part du prêteur restitué par apport.
        assert len(payouts) == 1
        assert payouts[0].allocation.lender_id == small.id

    def test_apport_rejected_on_closed_loan(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("100000"), suffix="CLOS")
        lender = _lender_with_tranche("100000")
        fr = request_funding(loan)
        _accept_all_consents(fr)
        tranche = LenderAllocation.objects.get(loan=loan, lender=lender).tranche
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut"])
        with pytest.raises(ApportError):
            restitute_tranche_by_apport(tranche.pk, admin_user=None)
