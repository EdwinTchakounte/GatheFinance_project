"""Intégrité du gel de garantie (2026-07-28).

Un snapshot de gel (``montant_gele_demandeur``) est figé à la demande et n'est
jamais ré-synchronisé à la baisse : si l'épargne qui le back fond ensuite
(placement restitué, etc.), l'engagement peut dépasser l'épargne réelle.

Invariant appliqué : le gel EFFECTIF est borné à l'épargne classique réellement
présente (on ne gèle jamais plus que ce qui existe). L'écart devient un « déficit
de collatéral » exposé, mais ne produit jamais un gel fantôme ni un disponible
négatif. Un crédit CLÔTURÉ libère tout (gel + déficit = 0).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.avaliste_services import member_frozen_guarantee
from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.services import generate_installments_flat_interest
from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.savings.services import classic_withdrawable


pytestmark = pytest.mark.django_db


def _savings(member, solde):
    account, _ = ClassicSavingsAccount.objects.update_or_create(
        member=member,
        defaults={"solde": Decimal(solde), "date_ouverture": date.today()},
    )
    return account


def _loan_with_gel(member, *, montant, gel, statut=Loan.Statut.ACTIF):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal(montant),
        duree_mois=3,
        motif="Intégrité gel",
        statut=LoanRequest.Statut.APPROUVEE,
        montant_gele_demandeur=Decimal(gel),
    )
    loan = Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier="GF-INTEG-1",
        montant=Decimal(montant),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=Decimal(montant) * Decimal("1.10"),
        solde_restant=Decimal(montant) * Decimal("1.10"),
        statut=statut,
    )
    generate_installments_flat_interest(loan)
    return loan


def test_frozen_guarantee_bounded_by_savings(active_member):
    _savings(active_member, "24000")  # épargne réelle
    _loan_with_gel(active_member, montant="200000", gel="124000")  # engagement figé
    # Effectif borné au solde réel ; l'engagement brut reste consultable.
    assert member_frozen_guarantee(active_member) == Decimal("24000")
    assert member_frozen_guarantee(active_member, effective=False) == Decimal("124000")


def test_withdrawable_never_negative_with_stale_gel(active_member):
    classic = _savings(active_member, "24000")
    _loan_with_gel(active_member, montant="200000", gel="124000")
    # Tout est gelé (collatéral < engagement) → 0 retirable, jamais négatif.
    assert classic_withdrawable(classic) == Decimal("0")


def test_partial_gel_leaves_the_rest_withdrawable(active_member):
    classic = _savings(active_member, "50000")
    _loan_with_gel(active_member, montant="100000", gel="20000")  # gel < solde
    # 50 000 − 20 000 gelé = 30 000 retirable.
    assert classic_withdrawable(classic) == Decimal("30000")


def test_loan_detail_effective_gel_and_deficit(active_member, admin_user):
    _savings(active_member, "24000")
    loan = _loan_with_gel(active_member, montant="200000", gel="124000")
    client = APIClient()
    client.force_authenticate(user=admin_user)
    r = client.get(f"/api/v1/loans/admin/{loan.id}/detail/")
    assert r.status_code == 200, r.content
    ms = r.json()["member_state"]
    assert Decimal(ms["gel_demandeur"]) == Decimal("24000")  # effectif borné
    assert Decimal(ms["gel_demandeur_engagement"]) == Decimal("124000")
    assert Decimal(ms["collateral_deficit"]) == Decimal("100000")


def test_cloture_loan_releases_gel_and_deficit(active_member, admin_user):
    _savings(active_member, "24000")
    loan = _loan_with_gel(
        active_member, montant="200000", gel="124000", statut=Loan.Statut.CLOTURE
    )
    client = APIClient()
    client.force_authenticate(user=admin_user)
    r = client.get(f"/api/v1/loans/admin/{loan.id}/detail/")
    ms = r.json()["member_state"]
    assert Decimal(ms["gel_demandeur"]) == Decimal("0")  # clôturé → libéré
    assert Decimal(ms["collateral_deficit"]) == Decimal("0")
