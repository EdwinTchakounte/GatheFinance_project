"""Règle 2026 « DATE BUTOIR UNIQUE » — l'échéancier crédit = 1 seule échéance.

Le membre ne rembourse plus selon une modalité (journalier/hebdo/mensuel) : il
rembourse LIBREMENT jusqu'à une date butoir unique, calculée depuis le montant
(paliers Art. 7). Le générateur ``generate_installments_flat_interest`` ne pose
donc plus qu'UNE échéance portant la totalité du dû, exigible à la date butoir.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.services import (
    _add_months,
    generate_installments_flat_interest,
)


pytestmark = pytest.mark.django_db


def _build_loan(borrower, *, montant, duree, mode_source):
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=Decimal(montant),
        duree_mois=duree,
        motif="Test échéance unique",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    net = Decimal(montant) * Decimal("0.90")
    loan = Loan.objects.create(
        member=borrower,
        loan_request=lr,
        numero_dossier=f"GF-CR-UNIQ-{duree}-{montant}",
        montant=Decimal(montant),
        taux_interet=Decimal("0.10"),
        duree_mois=duree,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=Decimal(montant) * Decimal("1.10"),
        solde_restant=Decimal(montant) * Decimal("1.10"),
        statut=Loan.Statut.ACTIF,
        mode_retenue_interets=(
            Loan.ModeRetenue.SOURCE if mode_source else Loan.ModeRetenue.ECHEANCES
        ),
        montant_decaisse_net=net if mode_source else Decimal(montant),
        interets_retenus_source=(
            Decimal(montant) * Decimal("0.10") if mode_source else Decimal("0")
        ),
    )
    return loan


class TestSingleDeadlineSchedule:
    def test_generates_exactly_one_installment(self, active_member):
        loan = _build_loan(active_member, montant="100000", duree=3, mode_source=False)
        installments = generate_installments_flat_interest(loan)
        assert len(installments) == 1
        assert loan.installments.count() == 1

    def test_installment_due_at_deadline(self, active_member):
        loan = _build_loan(active_member, montant="100000", duree=3, mode_source=False)
        generate_installments_flat_interest(loan)
        inst = loan.installments.get()
        # Date butoir = date_premiere_echeance + (durée − 1) mois.
        expected = _add_months(loan.date_premiere_echeance, loan.duree_mois - 1)
        assert inst.date_echeance == expected
        assert inst.numero_echeance == 1

    def test_legacy_mode_carries_full_capital_plus_interest(self, active_member):
        loan = _build_loan(active_member, montant="100000", duree=3, mode_source=False)
        generate_installments_flat_interest(loan)
        inst = loan.installments.get()
        assert Decimal(inst.montant_capital) == Decimal("100000.00")
        assert Decimal(inst.montant_interets) == Decimal("10000.00")
        assert Decimal(inst.montant_total) == Decimal("110000.00")

    def test_source_mode_installment_is_net_capital_only(self, active_member):
        loan = _build_loan(active_member, montant="100000", duree=3, mode_source=True)
        generate_installments_flat_interest(loan)
        inst = loan.installments.get()
        # Mode source : le membre ne rembourse que le net (90 %), 0 intérêt.
        assert Decimal(inst.montant_capital) == Decimal("90000.00")
        assert Decimal(inst.montant_interets) == Decimal("0.00")
        assert Decimal(inst.montant_total) == Decimal("90000.00")
