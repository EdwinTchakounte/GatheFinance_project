"""Durcissement « crédit non décaissé » (bug live 2026-07-28).

Un crédit approuvé est créé ACTIF avec ``en_attente_decaissement=True`` : l'argent
n'est versé qu'à l'étape admin de décaissement. Tant qu'il n'est pas décaissé, il
ne doit être NI remboursable, NI reconductible, NI ignoré par l'éligibilité — sinon
on produit un crédit « clôturé mais non décaissé » (argent jamais versé, collatéral
libéré, décaissement ensuite impossible), qui bloque en plus toute nouvelle demande.
Et l'admin doit pouvoir rattraper un crédit resté coincé (décaissement autorisé même
si le statut a été forcé à CLÔTURE).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.services import (
    approve_loan_request,
    compute_eligibility,
    disburse_loan_manual,
    request_loan_renewal,
)
from apps_coop.loans.transfer_services import (
    TransferError,
    repay_loan_from_savings,
)
from apps_coop.savings.models import ClassicSavingsAccount


pytestmark = pytest.mark.django_db(transaction=True)


def _approve_loan(member, admin_user, *, montant="100000"):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal(montant),
        duree_mois=6,
        motif="Test non décaissé",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
    )
    loan = approve_loan_request(
        lr,
        decided_by=admin_user,
        taux_annuel=Decimal("0.10"),
        date_premiere_echeance=date.today() + timedelta(days=30),
    )
    assert loan.en_attente_decaissement is True  # précondition
    return loan


def test_repayment_blocked_while_undisbursed(active_member, admin_user):
    loan = _approve_loan(active_member, admin_user)
    ClassicSavingsAccount.objects.create(
        member=active_member, solde=Decimal("500000"), date_ouverture=date.today()
    )
    with pytest.raises(TransferError, match="décaissé"):
        repay_loan_from_savings(loan, Decimal("10000"))
    loan.refresh_from_db()
    assert loan.statut == Loan.Statut.ACTIF
    assert loan.en_attente_decaissement is True


def test_reconduction_blocked_while_undisbursed(active_member, admin_user):
    loan = _approve_loan(active_member, admin_user)
    # Même arrivé à terme, un crédit non décaissé n'est pas reconductible.
    loan.date_butoire = date.today() - timedelta(days=1)
    loan.save(update_fields=["date_butoire"])
    with pytest.raises(ValueError, match="décaissé"):
        request_loan_renewal(loan)


def test_eligibility_counts_undisbursed_loan_as_in_progress(active_member, admin_user):
    # Un crédit ACTIF non décaissé bloque (couvert par le statut ACTIF).
    _approve_loan(active_member, admin_user)
    elig = compute_eligibility(active_member)
    assert elig.eligible is False
    assert any("en cours" in m for m in elig.motifs)


def test_cloture_loan_with_stale_undisbursed_flag_does_not_block(active_member, admin_user):
    """Régression 2026-07-28 : un membre qui a remboursé (crédit CLÔTURÉ) ne doit
    PAS rester bloqué à cause d'un flag `en_attente_decaissement` legacy."""
    loan = _approve_loan(active_member, admin_user)
    loan.statut = Loan.Statut.CLOTURE
    # Le flag legacy reste à True (donnée corrompue par l'ancien bug).
    loan.save(update_fields=["statut"])
    assert loan.en_attente_decaissement is True

    elig = compute_eligibility(active_member)
    assert elig.eligible is True  # plus de blocage : le crédit est clôturé
    assert not any("en cours" in m for m in elig.motifs)


def test_admin_can_disburse_a_stuck_cloture_loan(active_member, admin_user):
    """Récupération : un crédit forcé à CLÔTURE mais jamais décaissé peut être
    rattrapé — le décaissement le rebascule ACTIF et verse l'argent."""
    loan = _approve_loan(active_member, admin_user)
    # On simule l'anomalie : statut CLÔTURE alors que l'argent n'a pas été versé.
    loan.statut = Loan.Statut.CLOTURE
    loan.save(update_fields=["statut"])

    disburse_loan_manual(loan, agent=admin_user, reference_externe="RECOVERY-TEST")

    loan.refresh_from_db()
    assert loan.en_attente_decaissement is False
    assert loan.statut == Loan.Statut.ACTIF
