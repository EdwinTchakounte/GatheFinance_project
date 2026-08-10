"""Tests — Réforme garantie crédit 2026.

Couvre les règles introduites par la réforme :
  * Auto-couverture : épargne classique dispo ≥ montant → crédit sans avaliste,
    l'épargne propre du demandeur est gelée.
  * La collecte journalière NE compte PAS comme garantie (classique seul).
  * Gel avaliste = le MANQUE (montant − épargne dispo du demandeur).
  * Anti double-nantissement : une épargne déjà gelée n'est pas re-mobilisable.
  * Grisé au retrait : la part gelée est bloquée sur l'épargne classique.
  * Libération du gel au rejet de la demande et à la clôture du crédit.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.avaliste_services import (
    _member_available_savings,
    member_caution_capacity,
    member_frozen_guarantee,
    request_avaliste_consent,
    respond_to_avaliste_consent,
)
from apps_coop.loans.eligibility_routing import EligibilityRoute, evaluate_routes
from apps_coop.loans.models import AvalisteConsent, Loan, LoanRequest
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
from apps_coop.savings.services import classic_withdrawable

from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _senior(nom="DUPONT", *, classique=Decimal("0")):
    m = MemberFactory(nom=nom, date_adhesion=date.today() - timedelta(days=400))
    if classique:
        ClassicSavingsAccount.objects.create(
            member=m, solde=classique, date_ouverture=date.today()
        )
    return m


def _new(nom="MARTIN", *, classique=Decimal("0"), collecte=Decimal("0")):
    m = MemberFactory(nom=nom, date_adhesion=date.today() - timedelta(days=30))
    if classique:
        ClassicSavingsAccount.objects.create(
            member=m, solde=classique, date_ouverture=date.today()
        )
    if collecte:
        sa = SavingsAccount.objects.get(member=m)
        sa.solde = collecte
        sa.save(update_fields=["solde"])
    return m


def _classic_acc(member) -> ClassicSavingsAccount:
    return ClassicSavingsAccount.objects.get(member=member)


def _lr(member, montant=Decimal("50000")):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=3,
        motif="Test réforme garantie",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
    )


def _accept(lr, avaliste):
    consent = request_avaliste_consent(
        lr, numero_identification=avaliste.numero_membre, nom=avaliste.nom
    )
    return respond_to_avaliste_consent(consent, accept=True)


def _make_loan(lr, *, statut=Loan.Statut.ACTIF):
    today = date.today()
    return Loan.objects.create(
        loan_request=lr,
        member=lr.member,
        numero_dossier=f"DOS-{lr.pk}",
        montant=lr.montant_demande,
        taux_interet=Decimal("0.1000"),
        duree_mois=lr.duree_mois,
        date_decaissement=today,
        date_premiere_echeance=today + timedelta(days=30),
        montant_total_du=lr.montant_demande,
        solde_restant=lr.montant_demande,
        statut=statut,
    )


# ---------------------------------------------------------------------------
# Auto-couverture
# ---------------------------------------------------------------------------


class TestAutoCouverture:
    def test_new_member_self_covers_without_avaliste(self):
        m = _new(classique=Decimal("100000"))
        res = evaluate_routes(m, montant=Decimal("100000"))
        assert res.route == EligibilityRoute.SENIOR_BRC
        assert res.details["auto_couverture"] is True

    def test_collecte_does_not_count_as_guarantee(self):
        # 100k en collecte, 0 en classique → NE couvre PAS.
        m = _new(collecte=Decimal("100000"))
        res = evaluate_routes(m, montant=Decimal("100000"))
        assert res.route == EligibilityRoute.NONE

    def test_available_savings_is_classic_only(self):
        m = _new(classique=Decimal("40000"), collecte=Decimal("999999"))
        assert _member_available_savings(m) == Decimal("40000")


# ---------------------------------------------------------------------------
# Gel = le manque
# ---------------------------------------------------------------------------


class TestGelManque:
    def test_avaliste_covers_only_the_gap(self):
        borrower = _new(classique=Decimal("30000"))
        avaliste = _senior(classique=Decimal("100000"))
        lr = _lr(borrower, montant=Decimal("100000"))
        consent = request_avaliste_consent(
            lr, numero_identification=avaliste.numero_membre, nom=avaliste.nom
        )
        # Le demandeur gèle ses 30k, l'avaliste comble le manque (70k).
        lr.refresh_from_db()
        assert lr.montant_gele_demandeur == Decimal("30000")
        assert consent.montant_caution == Decimal("70000")

    def test_borrower_fully_covers_avaliste_gel_zero(self):
        # Épargne demandeur ≥ montant : l'avaliste ne gèle rien.
        borrower = _new(classique=Decimal("100000"))
        avaliste = _senior(classique=Decimal("100000"))
        lr = _lr(borrower, montant=Decimal("80000"))
        consent = request_avaliste_consent(
            lr, numero_identification=avaliste.numero_membre, nom=avaliste.nom
        )
        lr.refresh_from_db()
        assert lr.montant_gele_demandeur == Decimal("80000")
        assert consent.montant_caution == Decimal("0")

    def test_borrower_below_apport_min_is_rejected(self):
        # Décision cliente 2026-08 : l'avaliste couvre au MAX 80 % → le demandeur
        # doit apporter au moins 20 % (ici 5k < 20k pour un montant de 100k) → refus.
        borrower = _new(classique=Decimal("5000"))
        avaliste = _senior(classique=Decimal("500000"))
        lr = _lr(borrower, montant=Decimal("100000"))
        with pytest.raises(ValueError, match="Apport personnel insuffisant"):
            request_avaliste_consent(
                lr, numero_identification=avaliste.numero_membre, nom=avaliste.nom
            )


# ---------------------------------------------------------------------------
# Anti double-nantissement / cap-solde avaliste
# ---------------------------------------------------------------------------


class TestDoubleNantissement:
    def test_avaliste_capacity_reduced_by_prior_commitment(self):
        avaliste = _senior(classique=Decimal("100000"))
        # b1 apporte ses 20 % (12k), l'avaliste comble le reste (48k).
        b1 = _new(nom="BORROWER1", classique=Decimal("12000"))
        lr1 = _lr(b1, montant=Decimal("60000"))
        _accept(lr1, avaliste)  # 48k gelés chez l'avaliste

        # Capacité restante de l'avaliste = 100k − 48k = 52k.
        solde, engaged, free = member_caution_capacity(avaliste)
        assert engaged == Decimal("48000")
        assert free == Decimal("52000")

        # b2 demande 500k (apport 100k OK) mais couverture cumulée
        # (100k + 52k dispo avaliste) / 500k < 1 → KO.
        b2 = _new(nom="BORROWER2", classique=Decimal("100000"))
        lr2 = _lr(b2, montant=Decimal("500000"))
        with pytest.raises(ValueError, match="Couverture insuffisante"):
            request_avaliste_consent(
                lr2, numero_identification=avaliste.numero_membre, nom=avaliste.nom
            )


# ---------------------------------------------------------------------------
# Grisé au retrait + libération
# ---------------------------------------------------------------------------


class TestGriseRetrait:
    def test_avaliste_frozen_amount_reduces_withdrawable(self):
        avaliste = _senior(classique=Decimal("100000"))
        borrower = _new(classique=Decimal("12000"))  # apporte ses 20 %
        lr = _lr(borrower, montant=Decimal("60000"))
        _accept(lr, avaliste)  # 48k gelés chez l'avaliste

        acc = _classic_acc(avaliste)
        # Retirable = 100k − max(placement 0, gel 48k) = 52k.
        assert classic_withdrawable(acc) == Decimal("52000")
        assert member_frozen_guarantee(avaliste) == Decimal("48000")

    def test_rejected_request_releases_borrower_gel(self):
        borrower = _new(classique=Decimal("100000"))
        lr = _lr(borrower, montant=Decimal("100000"))
        lr.montant_gele_demandeur = Decimal("100000")
        lr.statut = LoanRequest.Statut.EN_ATTENTE
        lr.save(update_fields=["montant_gele_demandeur", "statut"])
        assert member_frozen_guarantee(borrower) == Decimal("100000")

        # Rejet → gel libéré.
        lr.statut = LoanRequest.Statut.REJETEE
        lr.save(update_fields=["statut"])
        assert member_frozen_guarantee(borrower) == Decimal("0")

    def test_cloture_releases_avaliste_caution(self):
        avaliste = _senior(classique=Decimal("100000"))
        borrower = _new(classique=Decimal("12000"))  # apporte ses 20 %
        lr = _lr(borrower, montant=Decimal("60000"))
        _accept(lr, avaliste)
        assert member_frozen_guarantee(avaliste) == Decimal("48000")

        # Le crédit est décaissé puis soldé → caution libérée.
        loan = _make_loan(lr, statut=Loan.Statut.ACTIF)
        assert member_frozen_guarantee(avaliste) == Decimal("48000")  # toujours gelé
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut"])
        assert member_frozen_guarantee(avaliste) == Decimal("0")
