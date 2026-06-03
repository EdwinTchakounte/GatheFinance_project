"""Tests des garde-fous d'éligibilité pour les demandes de crédit (A1).

Couvre :
  - Rule 2 (`compute_eligibility`) : un crédit en statut
    ACTIF / EN_RETARD / CONTENTIEUX bloque toute nouvelle demande — le
    membre doit solder avant d'en demander un autre.
  - Un crédit CLOTURE (soldé) ne bloque pas.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.services import compute_eligibility
from apps_coop.savings.models import SavingsAccount


pytestmark = pytest.mark.django_db


def _give_savings(member, solde: int = 100_000) -> SavingsAccount:
    """Garantit un solde suffisant pour passer Rule 4 (≥ 100 XAF), afin
    d'isoler Rule 2 lors des assertions.

    Purge également le cache de la reverse-OneToOne ``member.savings_account``
    pour que ``compute_eligibility(member)`` lise bien la valeur fraîche
    (MemberFactory crée un SavingsAccount à solde=0 et Django cache l'objet
    dès le premier accès sur l'instance de la fixture)."""
    account, _ = SavingsAccount.objects.get_or_create(
        member=member,
        defaults={"solde": Decimal(solde)},
    )
    if account.solde != Decimal(solde):
        account.solde = Decimal(solde)
        account.save(update_fields=["solde"])
    try:
        member._state.fields_cache.pop("savings_account", None)
    except AttributeError:
        pass
    return account


def _create_loan(member, *, statut: str, numero: str = "GF-CR-A1-001") -> Loan:
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Setup test A1",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier=numero,
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=30),
        date_premiere_echeance=date.today(),
        montant_total_du=Decimal("110000"),
        solde_restant=Decimal("50000"),
        statut=statut,
    )


class TestActiveLoanBlocksNewRequest:
    """A1 — un crédit non soldé empêche une nouvelle demande."""

    def test_eligible_when_no_existing_loan(self, active_member):
        _give_savings(active_member)
        result = compute_eligibility(active_member)
        assert result.eligible is True, result.motifs

    def test_active_loan_blocks(self, active_member):
        _give_savings(active_member)
        _create_loan(active_member, statut=Loan.Statut.ACTIF)
        result = compute_eligibility(active_member)
        assert result.eligible is False
        assert any("crédit" in m.lower() for m in result.motifs)

    def test_en_retard_loan_blocks(self, active_member):
        _give_savings(active_member)
        _create_loan(active_member, statut=Loan.Statut.EN_RETARD, numero="GF-CR-A1-RTD")
        result = compute_eligibility(active_member)
        assert result.eligible is False

    def test_contentieux_loan_blocks(self, active_member):
        _give_savings(active_member)
        _create_loan(active_member, statut=Loan.Statut.CONTENTIEUX, numero="GF-CR-A1-CTX")
        result = compute_eligibility(active_member)
        assert result.eligible is False

    def test_cloture_loan_does_not_block(self, active_member):
        """Un crédit soldé (CLOTURE) ne bloque plus de nouvelles demandes."""
        _give_savings(active_member)
        _create_loan(active_member, statut=Loan.Statut.CLOTURE, numero="GF-CR-A1-CLO")
        result = compute_eligibility(active_member)
        assert result.eligible is True, result.motifs
