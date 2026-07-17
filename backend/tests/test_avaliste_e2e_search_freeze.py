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

    def test_search_by_full_numero_membre(self, active_member):
        """Le mobile résout un avaliste tapé (numéro complet collé sans passer
        par la liste) → la recherche DOIT matcher le numéro exact et exposer
        une capacité de caution utilisable."""
        senior = _senior(
            nom="Ngassa", prenom="Zephirin", classique=Decimal("80000")
        )
        r = self._api(active_member).get(
            self.URL, {"q": senior.numero_membre}
        )
        assert r.status_code == 200, r.content
        row = next(
            (x for x in r.json()["results"]
             if x["numero_membre"] == senior.numero_membre),
            None,
        )
        assert row is not None, "numéro exact introuvable dans les résultats"
        assert Decimal(str(row["capacite_caution"])) > 0

    def test_junior_with_capacity_is_eligible(self, active_member):
        """Réforme garantie 2026 : l'ancienneté ne filtre plus rien.

        Un membre de la cohorte 2026 (< 12 mois, donc non senior) qui a
        l'épargne pour immobiliser le montant est un avaliste parfaitement
        valable. Avant, il était écarté silencieusement de la recherche — le
        mobile ne renvoyait « aucun résultat » sur un numéro pourtant exact.
        """
        junior = _new_member(classique=Decimal("80000"))
        junior.prenom = "Zephirin"
        junior.save(update_fields=["prenom"])

        r = self._api(active_member).get(self.URL, {"q": junior.numero_membre})
        assert r.status_code == 200, r.content
        row = next(
            (x for x in r.json()["results"]
             if x["numero_membre"] == junior.numero_membre),
            None,
        )
        assert row is not None, "un junior solvable doit rester trouvable"
        assert row["is_senior"] is False, "l'info reste exposée, mais ne filtre plus"
        assert Decimal(str(row["capacite_caution"])) == Decimal("80000")

    def test_junior_without_savings_has_no_capacity(self, active_member):
        """Corollaire : ce qui disqualifie, c'est la capacité — pas l'âge."""
        junior = _new_member()
        junior.prenom = "Zephirin"
        junior.save(update_fields=["prenom"])
        r = self._api(active_member).get(self.URL, {"q": junior.numero_membre})
        row = next(
            (x for x in r.json()["results"]
             if x["numero_membre"] == junior.numero_membre),
            None,
        )
        assert row is not None
        assert Decimal(str(row["capacite_caution"])) == Decimal("0")

    def test_search_hides_other_members_financials(self, active_member):
        """SÉCURITÉ : la recherche n'expose QUE la capacité de caution — pas le
        solde total ni les cautions engagées d'un autre membre."""
        senior = _senior(nom="Ngassa", prenom="Zephirin", classique=Decimal("80000"))
        r = self._api(active_member).get(self.URL, {"q": "ngass"})
        assert r.status_code == 200, r.content
        row = next(x for x in r.json()["results"]
                   if x["numero_membre"] == senior.numero_membre)
        assert "capacite_caution" in row
        assert "solde_total" not in row
        assert "cautions_engagees" not in row


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
