"""Régression : le funding manuel doit créer les ``LenderAllocation``.

Sans allocation, le partage 50/50 des intérêts est inerte : le prêteur est
notifié « les intérêts démarrent » mais ne touche jamais sa quote-part. Ce
test verrouille la correction du bug (compose funding manuel → allocation).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps_coop.audit.models import AppSetting
from apps_coop.loans.lender_admin_views import admin_compose_funding_manual
from apps_coop.loans.lender_payouts import _allocations_for_loan
from apps_coop.loans.models import (
    LenderAllocation,
    Loan,
    LoanRequest,
)
from apps_coop.loans.services import generate_installments_flat_interest
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from apps_coop.savings.models import LenderTranche
from tests.factories import MemberFactory


@pytest.fixture(autouse=True)
def _placement_window_open():
    """Placement fermé globalement au 1er août 2026 (closed_from) — on rouvre la
    fenêtre pour que le funding manuel (sur tranches de placement) reste testable
    après cette date."""
    AppSetting.objects.update_or_create(
        cle="savings.placement.closed_from", defaults={"valeur": "2099-01-01"}
    )


def _build_loan(borrower, *, montant=Decimal("100000")):
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=montant,
        duree_mois=3,
        motif="Test funding manuel",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    loan = Loan.objects.create(
        member=borrower,
        loan_request=lr,
        numero_dossier="GF-CR-MANUAL",
        montant=montant,
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=montant * Decimal("1.10"),
        solde_restant=montant * Decimal("1.10"),
        statut=Loan.Statut.ACTIF,
    )
    generate_installments_flat_interest(loan)
    return loan


def _make_lender_with_tranche(montant):
    AppSetting.objects.update_or_create(
        cle="lender.tranche.min_amount", defaults={"valeur": "1000"}
    )
    lender = MemberFactory()
    opt_in_lender(member=lender, is_global=False)
    add_tranche(member=lender, montant=Decimal(montant))
    return lender


def _compose(loan, selections, staff):
    factory = APIRequestFactory()
    request = factory.post(
        f"/api/v1/loans/admin/{loan.id}/funding-manual/",
        {"selections": selections},
        format="json",
    )
    force_authenticate(request, user=staff)
    return admin_compose_funding_manual(request, pk=loan.id)


@pytest.mark.django_db
def test_manual_funding_creates_allocation_and_pays_interest():
    staff = get_user_model().objects.create(
        username="admin1", is_staff=True, is_superuser=True
    )
    borrower = MemberFactory()
    loan = _build_loan(borrower, montant=Decimal("100000"))
    lender = _make_lender_with_tranche("100000")
    tranche = LenderTranche.objects.get(member=lender)

    resp = _compose(
        loan,
        [{"tranche_id": tranche.id, "montant": "100000"}],
        staff,
    )
    assert resp.status_code == 200, resp.data

    # Tranche engagée.
    tranche.refresh_from_db()
    assert tranche.statut == LenderTranche.Statut.ENGAGEE
    assert tranche.engaged_in_loan_id == loan.id

    # Allocation créée avec la bonne quote-part (100k / 100k = 1.0).
    alloc = LenderAllocation.objects.get(loan=loan, lender=lender)
    assert alloc.montant_alloue == Decimal("100000")
    assert alloc.quote_part == Decimal("1.00000000")

    # Le partage d'intérêts n'est plus inerte : la distribution retrouve
    # désormais l'allocation du prêteur (avant le fix, la liste était vide →
    # aucun reversement 50/50 possible).
    allocs = _allocations_for_loan(loan)
    assert list(allocs), "distribution inerte : aucune allocation liée au crédit"


@pytest.mark.django_db(transaction=True)
def test_compose_funding_locks_loan_inside_transaction(monkeypatch):
    """Régression prod : le verrou ``select_for_update()`` du Loan doit être
    posé DANS une transaction.

    En prod (PostgreSQL, ``ATOMIC_REQUESTS`` désactivé), appeler
    ``select_for_update()`` hors d'un bloc atomic lève
    ``TransactionManagementError`` → 500 « Composition impossible » à chaque
    clic sur Funding. Les autres tests ne l'attrapaient pas car pytest les
    enveloppe déjà dans une transaction ; on force donc ``transaction=True``
    pour reproduire le contexte NON atomique d'une vraie requête HTTP.

    On espionne ``QuerySet.select_for_update`` pour capturer l'état
    ``connection.in_atomic_block`` au moment exact où le Loan est verrouillé :
    sans ``@transaction.atomic`` sur la vue il serait ``False`` (bug), avec le
    fix il est ``True``.
    """
    from django.db import connection
    from django.db.models.query import QuerySet

    atomic_states: list[bool] = []
    real_sfu = QuerySet.select_for_update

    def spy_select_for_update(self, *args, **kwargs):
        atomic_states.append(connection.in_atomic_block)
        return real_sfu(self, *args, **kwargs)

    staff = get_user_model().objects.create(
        username="admin_tx", is_staff=True, is_superuser=True
    )
    borrower = MemberFactory()
    loan = _build_loan(borrower, montant=Decimal("100000"))
    lender = _make_lender_with_tranche("100000")
    tranche = LenderTranche.objects.get(member=lender)

    # On n'espionne QU'À PARTIR de l'appel de la vue : le setup ci-dessus
    # (opt_in_lender / add_tranche) fait ses propres select_for_update dans ses
    # transactions à lui et polluerait atomic_states[0].
    monkeypatch.setattr(QuerySet, "select_for_update", spy_select_for_update)

    resp = _compose(loan, [{"tranche_id": tranche.id, "montant": "100000"}], staff)

    assert resp.status_code == 200, resp.data
    # Le tout premier select_for_update = le verrou du Loan (ligne 247 de la
    # vue). Il DOIT être posé dans une transaction, sinon 500 en prod Postgres.
    assert atomic_states, "select_for_update jamais appelé — test invalide"
    assert atomic_states[0] is True, (
        "Le Loan est verrouillé hors transaction : select_for_update() lèvera "
        "TransactionManagementError en prod PostgreSQL (500 « Composition "
        "impossible »)."
    )


@pytest.mark.django_db
def test_partial_manual_funding_quote_part_is_prorata():
    staff = get_user_model().objects.create(
        username="admin2", is_staff=True, is_superuser=True
    )
    borrower = MemberFactory()
    loan = _build_loan(borrower, montant=Decimal("100000"))
    lender = _make_lender_with_tranche("40000")
    tranche = LenderTranche.objects.get(member=lender)

    resp = _compose(loan, [{"tranche_id": tranche.id, "montant": "40000"}], staff)
    assert resp.status_code == 200, resp.data

    alloc = LenderAllocation.objects.get(loan=loan, lender=lender)
    # 40 000 / 100 000 = 0.40 → le prêteur ne finance que 40 % du capital.
    assert alloc.quote_part == Decimal("0.40000000")
