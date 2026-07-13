"""Avaliste — E2E recherche élargie + cycle de gel (retouches 2026).

Couvre :
  #2a  Recherche live `/members/search-avaliste/` : matche désormais numéro,
       nom, PRÉNOM et TÉLÉPHONE (avant : numéro/nom seulement).
  #2b  Cycle complet du gel : désignation → acceptation → montant gelé sur le
       compte de l'avaliste → libération à la clôture du crédit garanti.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.avaliste_services import (
    member_caution_capacity,
    member_frozen_guarantee,
    request_avaliste_consent,
    respond_to_avaliste_consent,
)
from apps_coop.loans.models import AvalisteConsent, Loan, LoanRequest
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


def _senior(*, classique=Decimal("0"), **kwargs):
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=400), **kwargs)
    if classique > 0:
        ClassicSavingsAccount.objects.create(
            member=m, solde=classique, date_ouverture=date.today()
        )
    return m


def _new_member(*, classique=Decimal("0")):
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=30))
    if classique > 0:
        ClassicSavingsAccount.objects.create(
            member=m, solde=classique, date_ouverture=date.today()
        )
    return m


def _lr(member, montant=Decimal("50000")):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=3,
        motif="Test avaliste E2E",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
    )


# ---------------------------------------------------------------------------
# #2a — Recherche élargie
# ---------------------------------------------------------------------------


class TestSearchAvalisteBroadened:
    URL = "/api/v1/members/search-avaliste/"

    def _api(self, active_member):
        c = APIClient()
        c.force_authenticate(user=active_member.user)
        return c

    def test_search_by_prenom(self, active_member):
        senior = _senior(nom="Ngassa", prenom="Zephirin", phone="699112233")
        r = self._api(active_member).get(self.URL, {"q": "zeph"})
        assert r.status_code == 200, r.content
        nums = [x["numero_membre"] for x in r.json()["results"]]
        assert senior.numero_membre in nums

    def test_search_by_phone(self, active_member):
        senior = _senior(nom="Ngassa", prenom="Zephirin", phone="699112233")
        r = self._api(active_member).get(self.URL, {"q": "9911"})
        assert r.status_code == 200, r.content
        nums = [x["numero_membre"] for x in r.json()["results"]]
        assert senior.numero_membre in nums

    def test_search_by_nom_still_works(self, active_member):
        senior = _senior(nom="Ngassa", prenom="Zephirin", phone="699112233")
        r = self._api(active_member).get(self.URL, {"q": "ngass"})
        assert r.status_code == 200, r.content
        nums = [x["numero_membre"] for x in r.json()["results"]]
        assert senior.numero_membre in nums

    def test_non_senior_excluded(self, active_member):
        junior = _new_member()
        junior.prenom = "Zephirin"
        junior.save(update_fields=["prenom"])
        r = self._api(active_member).get(self.URL, {"q": "zeph"})
        nums = [x["numero_membre"] for x in r.json()["results"]]
        assert junior.numero_membre not in nums


# ---------------------------------------------------------------------------
# #2b — Cycle de gel complet
# ---------------------------------------------------------------------------


class TestAvalisteFreezeLifecycle:
    def _accepted(self):
        borrower = _new_member(classique=Decimal("10000"))
        senior = _senior(classique=Decimal("100000"))
        lr = _lr(borrower, Decimal("50000"))
        consent = request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom=senior.nom
        )
        return borrower, senior, lr, consent

    def test_pending_consent_not_yet_frozen(self):
        _, senior, _, _ = self._accepted()
        # Consentement PENDING → rien de gelé côté avaliste.
        assert member_frozen_guarantee(senior) == Decimal("0")

    def test_accept_freezes_montant_caution(self):
        _, senior, _, consent = self._accepted()
        respond_to_avaliste_consent(consent, accept=True)
        # Le manque (50k − 10k borrower) = 40k est gelé sur le compte avaliste.
        assert consent.montant_caution == Decimal("40000")
        assert member_frozen_guarantee(senior) == Decimal("40000")
        # Sa capacité de caution disponible chute d'autant.
        _, engaged, free = member_caution_capacity(senior)
        assert engaged == Decimal("40000")
        assert free == Decimal("60000")

    def test_freeze_released_on_loan_closure(self):
        _, senior, lr, consent = self._accepted()
        respond_to_avaliste_consent(consent, accept=True)
        assert member_frozen_guarantee(senior) == Decimal("40000")

        # Un crédit ACTIF garde le gel actif...
        loan = Loan.objects.create(
            member=lr.member,
            loan_request=lr,
            numero_dossier=f"E2E-{lr.member.numero_membre}",
            montant=Decimal("50000"),
            taux_interet=Decimal("0.10"),
            taux_penalite=Decimal("0.50"),
            duree_mois=3,
            date_decaissement=date.today(),
            date_premiere_echeance=date.today() + timedelta(days=30),
            montant_total_du=Decimal("55000"),
            solde_restant=Decimal("55000"),
            statut=Loan.Statut.ACTIF,
        )
        assert member_frozen_guarantee(senior) == Decimal("40000")

        # ...et la clôture libère la caution.
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut"])
        assert member_frozen_guarantee(senior) == Decimal("0")

    def test_refuse_never_freezes(self):
        _, senior, lr, consent = self._accepted()
        respond_to_avaliste_consent(consent, accept=False, motif="non")
        consent.refresh_from_db()
        assert consent.statut == AvalisteConsent.Statut.REFUSED
        assert member_frozen_guarantee(senior) == Decimal("0")
