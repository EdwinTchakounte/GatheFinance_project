"""Tests — garde-fou « apport personnel » (2026-07).

Règles produit validées :
  * Apport minimum disponible requis = ``loans.apport.min_available_rate`` (10 %).
    Rejet AUTOMATIQUE si la cagnotte (épargnes non gelées placées ou non +
    collecte) < 10 % du montant, avec un motif explicite.
  * À l'acceptation d'un dossier non auto-couvert et non avaliste, on gèle
    l'apport (le 10 %), transférable ensuite pour solder le crédit.
  * Les cas auto-couvert (épargne ≥ montant) et avaliste ne changent pas.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount

from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


def _seed_fee():
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais", "montant": Decimal("1000"), "actif": True},
    )


def _api(member):
    client = APIClient()
    client.force_authenticate(user=member.user)
    return client


def _ancient_brc(member, *, brc=True, months_ago=18):
    member.date_adhesion = date.today() - timedelta(days=30 * months_ago)
    member.is_brc_member = brc
    member.save(update_fields=["date_adhesion", "is_brc_member"])
    return member


def _seed_classic(member, amount):
    ClassicSavingsAccount.objects.update_or_create(
        member=member,
        defaults={"solde": Decimal(amount), "date_ouverture": date.today()},
    )


def _seed_collecte(member, amount):
    member.savings_account.solde = Decimal(amount)
    member.savings_account.save(update_fields=["solde"])


class TestApportGate:
    def test_reject_when_cagnotte_below_threshold(self, active_member):
        # Ancien + BRC (voie senior_brc ouverte), mais cagnotte quasi nulle.
        _seed_fee()
        _ancient_brc(active_member)
        _seed_classic(active_member, 5000)  # 5 % de 100000 < 10 % requis
        r = _api(active_member).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 403, r.content
        body = r.json()
        assert "Apport personnel insuffisant" in body["detail"]
        assert body["apport_requis"] == "10000"
        # Aucune demande créée.
        assert not LoanRequest.objects.filter(member=active_member).exists()

    def test_collecte_counts_towards_cagnotte(self, active_member):
        # 5000 classique + 6000 collecte = 11000 ≥ 10000 requis → accepté.
        _seed_fee()
        _ancient_brc(active_member)
        _seed_classic(active_member, 5000)
        _seed_collecte(active_member, 6000)
        r = _api(active_member).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 201, r.content

    def test_freeze_is_apport_not_all_available(self, active_member):
        # Ancien + BRC sous-couvert : gel = APPORT (20 %, G1) et non toute l'épargne.
        _seed_fee()
        _ancient_brc(active_member)
        _seed_classic(active_member, 30000)
        r = _api(active_member).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 201, r.content
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        assert lr.montant_gele_demandeur == Decimal("20000")  # 20 % × 100 000 (G1)
        assert lr.motif_gel_demandeur  # motif renseigné

    def test_self_covered_freezes_full_amount_unchanged(self, active_member):
        # Auto-couverture (épargne ≥ montant) : inchangé → gèle le montant plein.
        _seed_fee()
        _ancient_brc(active_member)
        _seed_classic(active_member, 100000)
        r = _api(active_member).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 201, r.content
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        assert lr.montant_gele_demandeur == Decimal("100000")

    def test_threshold_disabled_when_rate_zero(self, active_member):
        from apps_coop.audit.models import AppSetting

        AppSetting.objects.update_or_create(
            cle="loans.apport.min_available_rate",
            defaults={"valeur": "0", "description": ""},
        )
        _seed_fee()
        _ancient_brc(active_member)
        _seed_classic(active_member, 1)  # quasi rien
        r = _api(active_member).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 201, r.content
