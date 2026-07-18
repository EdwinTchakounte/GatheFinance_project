"""Lot B — endpoint admin ``/loans/admin/<pk>/detail/`` enrichi de l'ÉTAT
COMPLET de l'abonné sur le crédit (bouton « check » du dashboard).

Vérifie que la réponse porte un bloc ``member_state`` : voie d'obtention,
sous-couverture, gel demandeur, épargne (collecte + classique libre/placement/
gelé/dispo), avaliste, garantie matérielle, contentieux.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.services import generate_installments_flat_interest
from apps_coop.savings.models import ClassicSavingsAccount


pytestmark = pytest.mark.django_db


def _build_active_loan(member, *, montant=Decimal("90000"), gel=Decimal("30000")):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=3,
        motif="Test Lot B",
        statut=LoanRequest.Statut.APPROUVEE,
        montant_gele_demandeur=gel,
    )
    loan = Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier="GF-LOTB-1",
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


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_detail_exposes_member_state_block(active_member, admin_user):
    ClassicSavingsAccount.objects.update_or_create(
        member=active_member,
        defaults={"solde": Decimal("30000"), "date_ouverture": date.today()},
    )
    loan = _build_active_loan(active_member)  # gel 30 000 < montant 90 000

    r = _api(admin_user).get(f"/api/v1/loans/admin/{loan.id}/detail/")
    assert r.status_code == 200, r.content
    body = r.json()

    assert "member_state" in body
    ms = body["member_state"]
    # Voie senior_brc (pas d'avaliste, pas de campagne, pas de garantie mat).
    assert ms["voie"] == "senior_brc"
    # Gel 30 000 < demande 90 000 → sous-couverture (crédit de confiance).
    assert ms["sous_couverture"] is True
    assert Decimal(ms["gel_demandeur"]) == Decimal("30000")
    # Épargne classique exposée (libre/placement/gelé/dispo).
    assert ms["epargne"]["classique"] is not None
    assert Decimal(ms["epargne"]["classique"]["solde"]) == Decimal("30000")
    # Blocs contentieux présents (vides tant qu'il n'y a pas de saisie).
    assert ms["contentieux"]["epargne_saisie_at"] is None
    assert ms["avaliste"] is None


def test_detail_requires_staff(active_member):
    loan = _build_active_loan(active_member)
    # Membre simple (non staff) → refusé.
    r = _api(active_member.user).get(f"/api/v1/loans/admin/{loan.id}/detail/")
    assert r.status_code in (401, 403)
