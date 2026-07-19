"""Reconduction — encaissement des intérêts.

Avant ce lot, le membre lisait « tu verses les intérêts maintenant » mais rien
n'était payable : aucun montant persisté, le type ``frais_reconduction`` était
refusé par les trois canaux d'encaissement et aucun hook ne l'écoutait.

Règles couvertes ici :
  - le montant dû est FIGÉ à la demande (taux × montant reconduit, c.-à-d.
    tout ce qu'il reste à remettre : capital + intérêts résiduels) ;
  - le taux est piloté par l'admin (``RateParam``) ;
  - le versement est LIBRE : avant ou après la décision du comité, il ne
    bloque jamais l'approbation ;
  - les intérêts déjà encaissés ne sont pas re-facturés dans l'échéancier du
    nouveau dossier (sinon le membre paierait deux fois) ;
  - le prélèvement sur épargne ne mord ni sur le placement ni sur l'épargne
    gelée en garantie.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.loans.renewal_payment_services import (
    RenewalPaymentError,
    pay_renewal_interest_from_savings,
)
from apps_coop.loans.services import (
    approve_loan_renewal,
    approve_loan_request,
    request_loan_renewal,
)
from apps_coop.audit.models import AppSetting
from apps_coop.payments.models import RateParam
from apps_coop.savings.models import ClassicSavingsAccount

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(autouse=True)
def _mode_echeances(db):
    """Mode « intérêts aux échéances » — capital restant = montant emprunté.

    En mode « retenue à la source » le capital de référence serait le net
    décaissé (90 k pour 100 k), ce qui brouille les montants attendus ici.
    """
    AppSetting.objects.update_or_create(
        cle="loans.interest_withheld_at_source",
        defaults={"valeur": "false", "description": ""},
    )


@pytest.fixture
def comite_user(db):
    u = User.objects.create_user(
        email="comite-renew@gathe.test", password="x", username="comite-renew"
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u


def _loan(member, comite_user, montant=Decimal("100000")):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=3,
        motif="Crédit initial",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
    )
    return approve_loan_request(
        lr,
        decided_by=comite_user,
        taux_annuel=Decimal("0.10"),
        date_premiere_echeance=date.today() + timedelta(days=30),
    )


def _set_rate(code, valeur):
    RateParam.objects.update_or_create(
        code=code, defaults={"valeur": Decimal(valeur), "actif": True, "libelle": code}
    )


def _classic(member, solde):
    return ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(solde), date_ouverture=date.today()
    )


class TestMontantFige:
    def test_interets_dus_calcules_a_la_demande(self, active_member, comite_user):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)

        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        # Base = tout ce qu'il reste à remettre : 100 000 de capital
        # + 10 000 d'intérêts résiduels = 110 000. 15 % × 110 000 = 16 500.
        assert renewal.montant_a_reconduire_snapshot == Decimal("110000.00")
        assert renewal.interets_dus == Decimal("16500.00")
        assert renewal.reste_a_payer == Decimal("16500.00")
        assert renewal.interets_payes is False

    def test_taux_pilote_par_admin(self, active_member, comite_user):
        """Le pourcentage est éditable côté admin — pas de constante figée."""
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.20")
        loan = _loan(active_member, comite_user)

        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        # 20 % × 110 000 = 22 000.
        assert renewal.interets_dus == Decimal("22000.00")


class TestPrelevementSurEpargne:
    def test_preleve_et_marque_paye(self, active_member, comite_user):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        account = _classic(active_member, "50000")
        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        payment = pay_renewal_interest_from_savings(renewal)

        account.refresh_from_db()
        renewal.refresh_from_db()
        assert account.solde == Decimal("33500.00")  # 50 000 − 16 500
        assert payment.montant == Decimal("16500.00")
        assert renewal.interets_payes is True
        assert renewal.reste_a_payer == Decimal("0")
        assert renewal.frais_reconduction_payment_id == payment.id

    def test_refuse_si_epargne_insuffisante(self, active_member, comite_user):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        _classic(active_member, "1000")
        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        with pytest.raises(RenewalPaymentError, match="insuffisante"):
            pay_renewal_interest_from_savings(renewal)

    def test_second_prelevement_refuse(self, active_member, comite_user):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        _classic(active_member, "50000")
        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        pay_renewal_interest_from_savings(renewal)
        renewal.refresh_from_db()
        with pytest.raises(RenewalPaymentError, match="Aucun intérêt"):
            pay_renewal_interest_from_savings(renewal)


class TestVersementLibre:
    """« Directement ou même après, cela ne dérange pas. »"""

    def test_approbation_possible_sans_paiement_prealable(
        self, active_member, comite_user
    ):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.15"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # Non encaissés → reportés sur le nouveau dossier (110k + 16,5k).
        assert nouveau.montant_total_du == Decimal("126500.00")

    def test_paiement_apres_approbation_reste_possible(
        self, active_member, comite_user
    ):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        _classic(active_member, "50000")
        renewal = request_loan_renewal(loan, interets_au_comptant=False)
        approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.15"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        renewal.refresh_from_db()

        payment = pay_renewal_interest_from_savings(renewal)
        assert payment.montant == Decimal("16500.00")

    def test_paiement_avant_approbation_evite_le_double_comptage(
        self, active_member, comite_user
    ):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        _classic(active_member, "50000")
        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        pay_renewal_interest_from_savings(renewal)
        renewal.refresh_from_db()
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.15"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # Déjà encaissés → le nouveau dossier ne porte que la base (110k).
        assert nouveau.montant_total_du == Decimal("110000.00")


class TestEndpointsMembre:
    def test_liste_mes_reconductions(self, active_member, comite_user):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        request_loan_renewal(loan, interets_au_comptant=False)

        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.get("/api/v1/loans/me/renewals/")
        assert r.status_code == 200, r.content
        row = r.json()["results"][0]
        assert row["reste_a_payer"] == "16500.00"
        assert row["interets_payes"] is False
        assert row["numero_dossier"] == loan.numero_dossier

    def test_paiement_sur_epargne_via_api(self, active_member, comite_user):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        _classic(active_member, "50000")
        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.post(
            f"/api/v1/loans/renewals/{renewal.id}/pay-interest-from-savings/"
        )
        assert r.status_code == 200, r.content
        assert r.json()["renewal"]["interets_payes"] is True

    def test_epargne_insuffisante_renvoie_409(self, active_member, comite_user):
        _set_rate(RateParam.Code.RENEWAL_DEFERRED, "0.15")
        loan = _loan(active_member, comite_user)
        _classic(active_member, "100")
        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.post(
            f"/api/v1/loans/renewals/{renewal.id}/pay-interest-from-savings/"
        )
        assert r.status_code == 409, r.content

    def test_reconduction_d_un_autre_membre_invisible(
        self, active_member, comite_user
    ):
        from tests.factories import MemberFactory

        autre = MemberFactory()
        loan = _loan(autre, comite_user)
        renewal = request_loan_renewal(loan, interets_au_comptant=False)

        client = APIClient()
        client.force_authenticate(active_member.user)
        r = client.post(
            f"/api/v1/loans/renewals/{renewal.id}/pay-interest-from-savings/"
        )
        assert r.status_code == 404
