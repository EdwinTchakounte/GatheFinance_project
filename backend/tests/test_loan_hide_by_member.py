"""Le membre masque un crédit CLÔTURÉ de sa vue (soft-hide, rien en base).

- POST /loans/me/loans/<pk>/hide/ sur un crédit clôturé → masqué + exclu de
  /me/closed/.
- Masquer un crédit NON clôturé → 400.
- Rien n'est supprimé : la ligne Loan existe toujours en base.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import Loan, LoanRequest


pytestmark = pytest.mark.django_db(transaction=True)


def _loan(member, *, statut=Loan.Statut.CLOTURE):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("60000"),
        duree_mois=3,
        motif="Test hide",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier="GF-HIDE-1",
        montant=Decimal("60000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=90),
        date_premiere_echeance=date.today() - timedelta(days=60),
        montant_total_du=Decimal("66000"),
        solde_restant=Decimal("0"),
        statut=statut,
    )


def _api(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def test_hide_closed_loan_removes_it_from_closed_list(active_member):
    loan = _loan(active_member, statut=Loan.Statut.CLOTURE)
    client = _api(active_member)

    # Présent dans /me/closed/ avant.
    r0 = client.get("/api/v1/loans/me/closed/")
    assert any(x["id"] == loan.id for x in r0.json())

    r = client.post(f"/api/v1/loans/me/loans/{loan.id}/hide/")
    assert r.status_code == 200, r.content

    loan.refresh_from_db()
    assert loan.masque_par_membre is True
    # Toujours en base (rien supprimé), mais absent de la vue membre.
    assert Loan.objects.filter(pk=loan.id).exists()
    r1 = client.get("/api/v1/loans/me/closed/")
    assert all(x["id"] != loan.id for x in r1.json())


def test_cannot_hide_active_loan(active_member):
    loan = _loan(active_member, statut=Loan.Statut.ACTIF)
    r = _api(active_member).post(f"/api/v1/loans/me/loans/{loan.id}/hide/")
    assert r.status_code == 400


def test_hide_is_idempotent(active_member):
    loan = _loan(active_member, statut=Loan.Statut.CLOTURE)
    client = _api(active_member)
    assert client.post(f"/api/v1/loans/me/loans/{loan.id}/hide/").status_code == 200
    assert client.post(f"/api/v1/loans/me/loans/{loan.id}/hide/").status_code == 200
