"""Lot C — Filet de sécurité décaissement.

Un crédit approuvé est créé ACTIF avec un échéancier, mais l'argent n'est versé
qu'à l'étape admin de décaissement. Tant qu'il n'est pas décaissé
(``en_attente_decaissement=True``), le cron de retards ne doit NI marquer en
retard, NI pénaliser, NI passer en contentieux/saisie. Une fois décaissé, le
crédit redevient soumis au cron.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.services import (
    approve_loan_request,
    disburse_loan_manual,
)
from apps_coop.loans.tasks import suivi_retards_quotidien


pytestmark = pytest.mark.django_db(transaction=True)


def _approve_overdue_loan(member, admin_user, *, days_ago=400):
    """Approuve un crédit dont l'échéance est déjà dépassée (non décaissé)."""
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("60000"),
        duree_mois=6,
        motif="Test filet décaissement",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
    )
    return approve_loan_request(
        lr,
        decided_by=admin_user,
        taux_annuel=Decimal("0.10"),
        date_premiere_echeance=date.today() - timedelta(days=days_ago),
    )


def test_undisbursed_loan_is_skipped_by_cron(active_member, admin_user):
    loan = _approve_overdue_loan(active_member, admin_user)
    assert loan.en_attente_decaissement is True

    suivi_retards_quotidien()

    loan.refresh_from_db()
    # Aucune conséquence : ni retard, ni pénalité globale, ni saisie.
    assert loan.statut == Loan.Statut.ACTIF
    assert loan.penalite_globale_appliquee_at is None
    assert loan.epargne_saisie_at is None
    inst = loan.installments.first()
    assert inst is not None
    assert inst.statut != LoanInstallment.Statut.EN_RETARD


def test_disbursed_loan_is_processed_by_cron(active_member, admin_user):
    loan = _approve_overdue_loan(active_member, admin_user)
    # Décaissement manuel → lève le filet de sécurité.
    disburse_loan_manual(loan, agent=admin_user, reference_externe="TEST-DECAISS")
    loan.refresh_from_db()
    assert loan.en_attente_decaissement is False

    suivi_retards_quotidien()

    loan.refresh_from_db()
    # Décaissé + échéance dépassée → le cron agit : le crédit n'est plus ACTIF
    # intact et son échéance est marquée en retard (filet de sécurité levé).
    assert loan.statut in (Loan.Statut.EN_RETARD, Loan.Statut.CONTENTIEUX)
    inst = loan.installments.first()
    assert inst is not None
    assert inst.statut == LoanInstallment.Statut.EN_RETARD
