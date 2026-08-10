"""Validation END-TO-END du flow crédit complet (2026).

Déroule le cycle de vie réel des 3 voies via les endpoints membre (APIClient)
et les services admin (approbation, décaissement, consentement avaliste,
validation campagne), en assertant CHAQUE transition d'état, le gel de garantie
et les mouvements d'argent. Complète les tests unitaires par un parcours continu.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.loans.avaliste_services import respond_to_avaliste_consent
from apps_coop.loans.microcampaign_services import (
    accept_campaign_application,
    create_public_application,
)
from apps_coop.loans.models import (
    AvalisteConsent,
    Loan,
    LoanRequest,
    MicrocreditCampaign,
)
from apps_coop.loans.services import approve_loan_request, disburse_loan_manual
from apps_coop.loans.study_fee_services import (
    open_instruction_after_fees,
    pay_study_fee_from_savings,
)
from apps_coop.loans.transfer_services import (
    repay_loan_from_frozen,
    repay_loan_from_savings,
)
from apps_coop.members.models import Member
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount

from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db
User = get_user_model()

CREATE = "/api/v1/loans/requests/"
FUTURE = date.today() + timedelta(days=30)


def _seed_fee(amount="1000"):
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "F", "montant": Decimal(amount), "actif": True},
    )


@pytest.fixture
def comite(db):
    u = User.objects.create_user(
        username="e2e-comite", email="e2e-comite@t.test", password="x", is_staff=True
    )
    for g in ("comite", "coop_admin", "staff"):
        grp, _ = Group.objects.get_or_create(name=g)
        u.groups.add(grp)
    return u


def _api(obj):
    user = getattr(obj, "user", obj)  # accepte un Member ou un User
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _ancient_brc(m, months=18, brc=True):
    m.date_adhesion = date.today() - timedelta(days=30 * months)
    m.is_brc_member = brc
    m.save(update_fields=["date_adhesion", "is_brc_member"])
    return m


def _new(m, months=2):
    m.date_adhesion = date.today() - timedelta(days=30 * months)
    m.is_brc_member = False
    m.save(update_fields=["date_adhesion", "is_brc_member"])
    return m


def _classic(m, amt):
    ClassicSavingsAccount.objects.update_or_create(
        member=m, defaults={"solde": Decimal(amt), "date_ouverture": date.today()}
    )


def _campaign(fee=None, profil="commercants"):
    return MicrocreditCampaign.objects.create(
        nom="E2E camp", profil_cible=profil,
        date_debut=date.today() - timedelta(days=5),
        date_fin=date.today() + timedelta(days=30),
        montant_min=Decimal("5000"), montant_max=Decimal("50000"),
        taux_interet=Decimal("0.10"), nb_jours_recouvrement=60,
        actif=True, membre_requis=False,
        frais_etude_montant=(Decimal(fee) if fee is not None else None),
        created_by=UserFactory(),
    )


class TestVoieSeniorAutoCovered:
    """Senior/BRC auto-couvert : create → frais → instruction → approbation →
    décaissement → remboursement intégral → clôture (gel libéré)."""

    def test_full_lifecycle(self, active_member, comite):
        _seed_fee("1000")
        _ancient_brc(active_member)
        _classic(active_member, "250000")  # ≥ montant → auto-couverture + marge
        api = _api(active_member)

        r = api.post(CREATE, {"montant_demande": "100000", "duree_mois": 6, "motif": "e2e"}, format="json")
        assert r.status_code == 201, r.content
        assert r.json()["route"] == "senior_brc"
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE
        assert lr.montant_gele_demandeur == Decimal("100000")  # gèle le montant

        pay_study_fee_from_savings(lr)
        lr.refresh_from_db()
        assert lr.frais_demande_credit_paye is True
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION

        loan = approve_loan_request(lr, decided_by=comite, taux_annuel=Decimal("0.10"), date_premiere_echeance=FUTURE)
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.APPROUVEE
        assert loan.statut == Loan.Statut.ACTIF

        disburse_loan_manual(loan, agent=comite, reference_externe="E2E-A")
        loan.refresh_from_db()
        assert loan.en_attente_decaissement is False

        repay_loan_from_savings(loan, Decimal(loan.solde_restant))
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("0.00")
        assert loan.statut == Loan.Statut.CLOTURE


class TestVoieSeniorApportAndFrozenTransfer:
    """Senior/BRC sous-couvert : gel = apport 20 % (G1) + transfert du gelé pour solder."""

    def test_full_lifecycle(self, active_member, comite):
        _seed_fee("1000")
        _ancient_brc(active_member)
        _classic(active_member, "30000")  # 30 % = plancher d'éligibilité (G4)
        api = _api(active_member)

        r = api.post(CREATE, {"montant_demande": "100000", "duree_mois": 6, "motif": "e2e"}, format="json")
        assert r.status_code == 201, r.content
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        assert lr.montant_gele_demandeur == Decimal("20000")  # apport 20 % (G1)
        assert lr.motif_gel_demandeur

        pay_study_fee_from_savings(lr)
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION

        loan = approve_loan_request(lr, decided_by=comite, taux_annuel=Decimal("0.10"), date_premiere_echeance=FUTURE)
        disburse_loan_manual(loan, agent=comite, reference_externe="E2E-B")
        loan.refresh_from_db()
        before = Decimal(loan.solde_restant)

        repay_loan_from_frozen(loan)  # transfère l'apport gelé
        loan.refresh_from_db()
        lr.refresh_from_db()
        assert Decimal(loan.solde_restant) == before - Decimal("20000")
        assert lr.montant_gele_demandeur == Decimal("0")


class TestVoieAvaliste:
    """Avaliste « D'ABORD » (2026-07-28) : create → sollicitation + gel réparti
    (EN_ATTENTE_AVALISTE) → acceptation avaliste → frais exigibles (EN_ATTENTE)
    → règlement → instruction → approbation. Les frais ne sont payables
    qu'APRÈS l'acceptation de l'avaliste."""

    def test_full_lifecycle(self, active_member, comite):
        _seed_fee("1000")
        _new(active_member)
        _classic(active_member, "20000")  # apport 20 % du montant (100k)
        avaliste = MemberFactory(nom="DUPONT")
        _ancient_brc(avaliste)
        _classic(avaliste, "200000")
        api = _api(active_member)

        r = api.post(CREATE, {
            "montant_demande": "100000", "duree_mois": 6, "motif": "e2e",
            "avaliste_numero": avaliste.numero_membre, "avaliste_nom": "DUPONT",
        }, format="json")
        assert r.status_code == 201, r.content
        assert r.json()["route"] == "avaliste"
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        # Avaliste sollicité DÈS la création : frais pas encore exigibles.
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE_AVALISTE
        assert lr.frais_demande_credit_paye is False
        consent = lr.avaliste_consent
        assert consent.statut == AvalisteConsent.Statut.PENDING
        assert consent.montant_caution > 0  # l'avaliste comble le manque

        # Acceptation → la porte des frais s'ouvre (EN_ATTENTE).
        respond_to_avaliste_consent(consent, accept=True)
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE
        assert lr.avaliste_id == avaliste.id

        # Frais réglés APRÈS acceptation → instruction. En voie avaliste, toute
        # l'épargne classique du demandeur est gelée en garantie → il règle les
        # frais par Mobile Money / agence (canal représenté ici par le hook
        # d'ouverture d'instruction), pas depuis son épargne.
        open_instruction_after_fees(lr)
        lr.refresh_from_db()
        assert lr.frais_demande_credit_paye is True
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION

        loan = approve_loan_request(lr, decided_by=comite, taux_annuel=Decimal("0.10"), date_premiere_echeance=FUTURE)
        assert loan.statut == Loan.Statut.ACTIF

    def test_avaliste_refuse_termine_en_rejet(self, active_member, comite):
        _seed_fee("1000")
        _new(active_member)
        _classic(active_member, "20000")
        avaliste = MemberFactory(nom="DUPONT")
        _ancient_brc(avaliste)
        _classic(avaliste, "200000")
        r = _api(active_member).post(CREATE, {
            "montant_demande": "100000", "duree_mois": 6, "motif": "e2e",
            "avaliste_numero": avaliste.numero_membre, "avaliste_nom": "DUPONT",
        }, format="json")
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        # Avaliste sollicité d'abord ; refus AVANT tout paiement de frais.
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE_AVALISTE
        respond_to_avaliste_consent(lr.avaliste_consent, accept=False, motif="indispo")
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.REJETEE_AVALISTE
        assert lr.frais_demande_credit_paye is False  # rien encaissé


class TestVoieCampaignMember:
    """Campagne (membre) fee=0 : create → EN_VALIDATION_CAMPAGNE → comité valide
    (saute les frais) → instruction → approbation. Pas de gel."""

    def test_full_lifecycle(self, active_member, comite):
        _seed_fee("1000")
        _new(active_member)
        camp = _campaign(fee="0")
        api = _api(active_member)

        r = api.post(CREATE, {"montant_demande": "25000", "duree_mois": 6, "motif": "e2e", "campaign_id": camp.id}, format="json")
        assert r.status_code == 201, r.content
        assert r.json()["route"] == "campaign"
        # Campagne → EN_VALIDATION_CAMPAGNE : aucun frais n'est réglable à la
        # soumission (ils ne seraient dus qu'APRÈS validation de l'activité, et
        # ici l'étude est gratuite). Le membre ne doit donc PAS se voir proposer
        # de paiement — `frais_a_payer` est null (sinon le paiement échouait avec
        # « Cette demande n'attend pas de frais »).
        assert r.json()["frais_a_payer"] is None
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        assert lr.statut == LoanRequest.Statut.EN_VALIDATION_CAMPAGNE

        rd = _api(comite).post(f"/api/v1/loans/admin/requests/{lr.id}/campaign-decide/", {"decision": "valide"}, format="json")
        assert rd.status_code == 200, rd.content
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION  # frais 0 sautés

        loan = approve_loan_request(lr, decided_by=comite, taux_annuel=Decimal("0.10"), date_premiere_echeance=FUTURE)
        assert loan.statut == Loan.Statut.ACTIF
        lr.refresh_from_db()
        assert lr.montant_gele_demandeur == Decimal("0")  # campagne = pas de gel


class TestVoieCampaignVisitor:
    """Campagne (visiteur non-membre) : candidature vitrine → acceptation admin
    → compte membre créé + LoanRequest ouvert."""

    def test_visitor_to_beneficiary(self, comite):
        _seed_fee("1000")
        camp = _campaign(fee="0")  # membre_requis=False
        app = create_public_application(
            camp, nom="Doe", prenom="Jane", phone="690000000",
            email="jane.e2e@t.test", montant=Decimal("20000"), motif="e2e",
        )
        assert app.pk is not None

        accept_campaign_application(app, decided_by=comite)

        m = Member.objects.filter(user__email="jane.e2e@t.test").first()
        assert m is not None
        assert m.statut == Member.Statut.ACTIF
        assert LoanRequest.objects.filter(member=m).exists()
