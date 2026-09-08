"""Onglet « Notifications » admin — échéances de fin de chaque processus.

Ce que ces tests figent :
  - chaque processus surveillé produit une carte, même vide (une carte qui
    disparaît laisse croire à un oubli) ;
  - la gravité reflète bien le dépassement, et une carte vide ne crie jamais
    au loup ;
  - le tri remonte l'urgent en premier ;
  - c'est une vue de LECTURE : elle ne modifie ni n'envoie rien ;
  - l'accès est gouverné par la ressource RBAC `notifications`.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.deadlines import collect_deadlines, deadlines_summary
from apps_coop.loans.models import Loan, LoanRequest, MicrocreditCampaign
from apps_coop.members.models import Member
from apps_coop.members.resources import RESOURCE_KEYS
from apps_coop.notifications.models import EmailLog
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
from apps_coop.special_collections.models import SpecialCollectionCycle
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/audit/admin/deadlines/"
TODAY = date.today()


def _superuser():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m.user


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _campagne(*, actif=True, fin_offset=-5):
    return MicrocreditCampaign.objects.create(
        nom="Campagne test",
        profil_cible="commercants",
        date_debut=TODAY - timedelta(days=60),
        date_fin=TODAY + timedelta(days=fin_offset),
        montant_min=Decimal("5000"),
        montant_max=Decimal("50000"),
        taux_interet=Decimal("0.10"),
        nb_jours_recouvrement=60,
        actif=actif,
        created_by=_superuser(),
    )


def _carte(cartes, cle):
    return next(c for c in cartes if c["cle"] == cle)


def _loan_depasse(jours):
    """Crédit dont la date butoire est passée de `jours` jours."""
    member = MemberFactory()
    req = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test échéances",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        loan_request=req,
        member=member,
        numero_dossier=f"TEST-{member.id}",
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        modalite_paiement="mensuel",
        date_decaissement=TODAY - timedelta(days=180),
        date_premiere_echeance=TODAY - timedelta(days=150),
        date_butoire=TODAY - timedelta(days=jours),
        montant_total_du=Decimal("110000"),
        solde_restant=Decimal("50000"),
        statut=Loan.Statut.EN_RETARD,
        en_attente_decaissement=False,
    )


# --- Le catalogue de processus ----------------------------------------------


class TestCatalogue:
    def test_tous_les_processus_surveilles_sont_presents(self):
        cles = {c["cle"] for c in collect_deadlines()}
        assert cles == {
            "collecte.fin_de_mois",
            "credit.echeance_depassee",
            "credit.echeance_proche",
            "campagne.echue",
            "campagne.fin_proche",
            "collecte_particuliere.fin_cycle",
            "epargne.maturite",
            "membre.reinscription",
        }

    def test_une_carte_vide_reste_affichee(self):
        """Savoir qu'il n'y a rien à traiter est une information."""
        carte = _carte(collect_deadlines(), "credit.echeance_depassee")
        assert carte["volume"] == 0
        assert carte["titre"]
        assert carte["lien"]

    def test_une_carte_vide_ne_crie_pas_au_loup(self):
        """Sans élément concerné, pas d'alerte rouge même si la date est passée."""
        carte = _carte(collect_deadlines(), "credit.echeance_depassee")
        assert carte["gravite"] == "info"


# --- Détection par processus ------------------------------------------------


class TestDetection:
    def test_credit_depasse_detecte_et_marque_urgent(self):
        _loan_depasse(10)

        carte = _carte(collect_deadlines(), "credit.echeance_depassee")

        assert carte["volume"] == 1
        assert carte["en_retard"] is True
        assert carte["gravite"] == "urgent"
        assert carte["jours_restants"] == -10

    def test_credit_non_decaisse_exclu(self):
        """Pas d'argent versé = pas de retard imputable au membre."""
        loan = _loan_depasse(10)
        loan.en_attente_decaissement = True
        loan.save(update_fields=["en_attente_decaissement"])

        assert _carte(collect_deadlines(), "credit.echeance_depassee")["volume"] == 0

    def test_credit_cloture_exclu(self):
        loan = _loan_depasse(10)
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut"])

        assert _carte(collect_deadlines(), "credit.echeance_depassee")["volume"] == 0

    def test_campagne_echue_encore_active_detectee(self):
        _campagne(actif=True)

        carte = _carte(collect_deadlines(), "campagne.echue")
        assert carte["volume"] == 1
        assert carte["gravite"] == "urgent"

    def test_campagne_deja_fermee_ignoree(self):
        _campagne(actif=False)
        assert _carte(collect_deadlines(), "campagne.echue")["volume"] == 0

    def test_cycle_de_collecte_a_cloturer_detecte(self):
        SpecialCollectionCycle.objects.create(
            type="caisse_scolaire", nom="Caisse 2026",
            date_debut=TODAY - timedelta(days=200),
            date_fin=TODAY - timedelta(days=2),
            statut=SpecialCollectionCycle.Statut.OUVERT,
        )

        carte = _carte(collect_deadlines(), "collecte_particuliere.fin_cycle")
        assert carte["volume"] == 1
        assert carte["en_retard"] is True

    def test_cycle_deja_clos_ignore(self):
        SpecialCollectionCycle.objects.create(
            type="caisse_scolaire", nom="Caisse close",
            date_debut=TODAY - timedelta(days=200),
            date_fin=TODAY - timedelta(days=2),
            statut=SpecialCollectionCycle.Statut.CLOS,
        )
        assert _carte(collect_deadlines(), "collecte_particuliere.fin_cycle")["volume"] == 0

    def test_epargne_a_maturite_detectee(self):
        ClassicSavingsAccount.objects.create(
            member=MemberFactory(), solde=Decimal("50000"),
            date_ouverture=TODAY - timedelta(days=365),
            date_prochaine_maturite=TODAY + timedelta(days=3),
        )

        carte = _carte(collect_deadlines(), "epargne.maturite")
        assert carte["volume"] == 1
        assert carte["gravite"] == "proche"

    def test_reinscription_due_detectee(self):
        member = MemberFactory()
        member.statut = Member.Statut.ACTIF
        member.date_derniere_reinscription = TODAY - timedelta(days=366)
        member.save(update_fields=["statut", "date_derniere_reinscription"])

        carte = _carte(collect_deadlines(), "membre.reinscription")
        assert carte["volume"] == 1
        assert carte["en_retard"] is True

    def test_membre_recent_pas_dans_les_reinscriptions(self):
        member = MemberFactory()
        member.date_derniere_reinscription = TODAY
        member.save(update_fields=["date_derniere_reinscription"])

        assert _carte(collect_deadlines(), "membre.reinscription")["volume"] == 0

    def test_collecte_fin_de_mois_compte_les_comptes_approvisionnes(self):
        m1, m2 = MemberFactory(), MemberFactory()
        SavingsAccount.objects.filter(member=m1).update(solde=Decimal("5000"))
        SavingsAccount.objects.filter(member=m2).update(solde=Decimal("0"))

        carte = _carte(collect_deadlines(), "collecte.fin_de_mois")
        assert carte["volume"] == 1
        # Toujours le 1er du mois suivant.
        assert carte["date_echeance"].endswith("-01")


# --- Horizon et tri ---------------------------------------------------------


class TestHorizonEtTri:
    def test_horizon_borne_ce_qui_remonte(self):
        ClassicSavingsAccount.objects.create(
            member=MemberFactory(), solde=Decimal("50000"),
            date_ouverture=TODAY,
            date_prochaine_maturite=TODAY + timedelta(days=90),
        )

        assert _carte(collect_deadlines(horizon_days=30), "epargne.maturite")["volume"] == 0
        assert _carte(collect_deadlines(horizon_days=120), "epargne.maturite")["volume"] == 1

    def test_lurgent_remonte_en_premier(self):
        _loan_depasse(30)
        cartes = collect_deadlines()
        assert cartes[0]["gravite"] == "urgent"

    def test_summary_compte_ce_qui_brule(self):
        _loan_depasse(10)
        cartes = collect_deadlines()

        s = deadlines_summary(cartes)
        assert s["urgent"] >= 1
        assert s["a_traiter"] >= 1
        assert s["total_elements"] >= 1


# --- Endpoint ---------------------------------------------------------------


class TestEndpoint:
    def test_superuser_recoit_cartes_et_compteurs(self):
        _loan_depasse(5)

        res = _api(_superuser()).get(URL)

        assert res.status_code == 200
        body = res.json()
        assert body["horizon_days"] == 30
        assert body["summary"]["urgent"] >= 1
        assert len(body["results"]) == 8

    def test_horizon_personnalise_respecte(self):
        res = _api(_superuser()).get(f"{URL}?horizon=90")
        assert res.json()["horizon_days"] == 90

    def test_horizon_absurde_borne(self):
        """Un horizon délirant ferait balayer toute la base."""
        assert _api(_superuser()).get(f"{URL}?horizon=99999").json()["horizon_days"] == 365
        assert _api(_superuser()).get(f"{URL}?horizon=-5").json()["horizon_days"] == 1
        assert _api(_superuser()).get(f"{URL}?horizon=abc").json()["horizon_days"] == 30

    def test_membre_simple_refuse(self):
        assert _api(MemberFactory().user).get(URL).status_code in (401, 403)

    def test_anonyme_refuse(self):
        assert APIClient().get(URL).status_code in (401, 403)

    def test_la_ressource_rbac_est_declaree(self):
        """Sans entrée au registre, le rôle ne serait pas cochable côté admin."""
        assert "notifications" in RESOURCE_KEYS


# --- C'est une vue de LECTURE -----------------------------------------------


def test_la_consultation_nenvoie_rien_et_ne_modifie_rien():
    """L'onglet rend visible ; ce sont les crons qui agissent."""
    _loan_depasse(10)
    loan_avant = Loan.objects.get()
    emails_avant = EmailLog.objects.count()

    _api(_superuser()).get(URL)

    loan_apres = Loan.objects.get()
    assert loan_apres.statut == loan_avant.statut
    assert loan_apres.solde_restant == loan_avant.solde_restant
    assert EmailLog.objects.count() == emails_avant
