"""Tests LOT 15 — Routing 3 voies câblé dans POST /loans/requests/.

Intégration end-to-end via le endpoint : vérifie que la vue dispatche
correctement vers la bonne voie en fonction des champs fournis et de
l'état du membre.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import (
    AvalisteConsent,
    LoanRequest,
    MicrocreditCampaign,
)
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount

from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_fee():
    """La vue requiert un FeeType DEMANDE_CREDIT actif."""
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={
            "libelle": "Frais de demande de crédit",
            "montant": Decimal("1000"),
            "actif": True,
        },
    )


def _api(member):
    client = APIClient()
    # Ajouter au groupe 'members' si ton ApiPermission le demande — pour le
    # endpoint /loans/requests/ on a juste besoin d'être authentifié comme
    # IsActiveMember (statut=actif + un Member lié).
    client.force_authenticate(user=member.user)
    return client


def _ancient_brc(member, *, brc=True, months_ago=18):
    member.date_adhesion = date.today() - timedelta(days=30 * months_ago)
    member.is_brc_member = brc
    member.save(update_fields=["date_adhesion", "is_brc_member"])
    return member


def _new_member(member, months_ago=2):
    member.date_adhesion = date.today() - timedelta(days=30 * months_ago)
    member.is_brc_member = False
    member.save(update_fields=["date_adhesion", "is_brc_member"])
    return member


def _seed_savings(member, amount):
    member.savings_account.solde = Decimal(amount)
    member.savings_account.save(update_fields=["solde"])


def _seed_classic(member, amount):
    ClassicSavingsAccount.objects.update_or_create(
        member=member,
        defaults={"solde": Decimal(amount), "date_ouverture": date.today()},
    )


def _open_campaign(profil="commercants"):
    today = date.today()
    return MicrocreditCampaign.objects.create(
        nom="Campagne test LOT 15",
        profil_cible=profil,
        date_debut=today - timedelta(days=5),
        date_fin=today + timedelta(days=30),
        montant_min=Decimal("5000"),
        montant_max=Decimal("50000"),
        taux_interet=Decimal("0.10"),
        nb_jours_recouvrement=60,
        actif=True,
        created_by=UserFactory(),
    )


# ---------------------------------------------------------------------------
# Voie 1 — SENIOR_BRC
# ---------------------------------------------------------------------------


class TestVoieSeniorBrc:
    def test_self_coverage_creates_lr_en_attente(self, active_member):
        # Réforme 2026 : épargne classique ≥ montant → auto-couverture directe.
        _seed_fee()
        _new_member(active_member)
        _seed_classic(active_member, 100000)
        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["route"] == "senior_brc"
        assert body["loan_request"]["statut"] == "en_attente"
        # L'épargne propre du demandeur est gelée en garantie (= montant).
        lr = LoanRequest.objects.get(pk=body["loan_request"]["id"])
        assert lr.montant_gele_demandeur == Decimal("100000")

    def test_ancient_brc_undercovered_creates_lr_with_apport_gel(
        self, active_member
    ):
        # Ancien + BRC, épargne classique < montant : dossier accepté en voie 1
        # (le comité jugera), SANS avaliste. Depuis le garde-fou apport (2026-07),
        # le gel = l'APPORT personnel (10 % du montant), transférable pour solder,
        # et non plus toute l'épargne dispo.
        _seed_fee()
        _ancient_brc(active_member)
        _seed_classic(active_member, 30000)
        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "100000",
                "duree_mois": 6,
                "motif": "Crédit de confiance ancien BRC",
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["route"] == "senior_brc"
        lr = LoanRequest.objects.get(pk=body["loan_request"]["id"])
        # Gel = apport personnel 20 % × 100 000 = 20 000 (G1), borné à l'épargne
        # dispo (30 000 ici → 20 000).
        assert lr.montant_gele_demandeur == Decimal("20000")

    def test_above_self_coverage_without_avaliste_rejects(self, active_member):
        # Un NOUVEL adhérent (non ancien) sans avaliste dont l'épargne n'atteint
        # même pas l'apport requis (30 % × 500 000 = 150 000) → aucune voie (403).
        _seed_fee()
        _new_member(active_member)
        _seed_classic(active_member, 10000)  # 2 % < 30 % requis
        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {"montant_demande": "500000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 403
        assert any("apport" in m.lower() for m in r.json()["motifs"])

    def test_insufficient_coverage_no_avaliste_falls_through_to_none(
        self, active_member
    ):
        """Épargne < apport requis (30 %) + sans avaliste/campaign → aucune voie."""
        _seed_fee()
        _new_member(active_member)
        _seed_classic(active_member, 20000)  # 20 % < 30 % requis
        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 403
        body = r.json()
        assert "motifs" in body
        assert any("apport" in m.lower() for m in body["motifs"])


# ---------------------------------------------------------------------------
# Voie 2 — AVALISTE
# ---------------------------------------------------------------------------


class TestVoieAvaliste:
    def test_new_member_with_valid_avaliste_creates_lr_en_attente_frais(
        self, active_member
    ):
        """Porte des frais 2026 : « frais d'abord, avaliste ensuite ».

        La demande naît en ``en_attente`` (frais à payer) et la désignation est
        mémorisée. L'avaliste n'est PAS sollicité tant que les 5000 XAF ne sont
        pas encaissés — inutile de déranger un tiers sur un dossier que le
        demandeur n'a pas encore validé en payant. Le consentement et le gel
        sont posés à l'encaissement (cf. test_study_fee_gate_2026).
        """
        _seed_fee()
        _new_member(active_member)
        _seed_classic(active_member, 20000)  # apport 20 % du montant
        avaliste = MemberFactory(nom="DUPONT")
        _ancient_brc(avaliste)
        _seed_classic(avaliste, 200000)  # couverture suffisante

        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "100000",
                "duree_mois": 6,
                "motif": "Test avaliste",
                "avaliste_numero": avaliste.numero_membre,
                "avaliste_nom": "DUPONT",
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["route"] == "avaliste"
        # « Avaliste D'ABORD » (2026-07-28) : la demande naît en attente de la
        # réponse de l'avaliste, sollicité dès la soumission. Les frais ne sont
        # exigibles qu'après son acceptation.
        assert body["loan_request"]["statut"] == "en_attente_avaliste"

        lr = LoanRequest.objects.get(pk=body["loan_request"]["id"])
        assert hasattr(lr, "avaliste_consent"), (
            "l'avaliste doit être sollicité dès la soumission (avaliste d'abord)"
        )
        assert lr.frais_demande_credit_paye is False
        # La désignation est mémorisée.
        assert lr.avaliste_numero_saisi == avaliste.numero_membre
        assert lr.avaliste_nom_saisi == "DUPONT"

        # À l'encaissement, l'avaliste est sollicité et le gel se pose :
        # le demandeur gèle son apport (20k = 20 %), l'avaliste comble le reste
        # jusqu'à 100 % (100k − 20k = 80k, plafond avaliste 80 %).
        from apps_coop.loans.study_fee_services import open_instruction_after_fees

        open_instruction_after_fees(lr)

        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE_AVALISTE
        assert lr.avaliste_consent.statut == AvalisteConsent.Statut.PENDING
        assert lr.montant_gele_demandeur == Decimal("20000")
        assert lr.avaliste_consent.montant_caution == Decimal("80000")

    def test_insufficient_coverage_rejects(self, active_member):
        _seed_fee()
        _new_member(active_member)
        avaliste = MemberFactory(nom="DUPONT")
        _ancient_brc(avaliste)
        _seed_savings(avaliste, 5000)  # couverture insuffisante

        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "100000",
                "duree_mois": 6,
                "motif": "Test",
                "avaliste_numero": avaliste.numero_membre,
                "avaliste_nom": "DUPONT",
            },
            format="json",
        )
        assert r.status_code == 403
        body = r.json()
        assert any("Couverture" in m for m in body["motifs"])

    def test_wrong_nom_rejects(self, active_member):
        _seed_fee()
        _new_member(active_member)
        avaliste = MemberFactory(nom="DUPONT")
        _ancient_brc(avaliste)
        _seed_savings(avaliste, 200000)

        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "100000",
                "duree_mois": 6,
                "motif": "Test",
                "avaliste_numero": avaliste.numero_membre,
                "avaliste_nom": "WRONGNAME",
            },
            format="json",
        )
        assert r.status_code == 403

    def test_avaliste_must_be_senior(self, active_member):
        _seed_fee()
        _new_member(active_member)
        # Avaliste pas senior — doit échouer.
        new_avaliste = MemberFactory(nom="DUPONT")
        _new_member(new_avaliste, months_ago=3)
        _seed_savings(new_avaliste, 500000)

        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "100000",
                "duree_mois": 6,
                "motif": "Test",
                "avaliste_numero": new_avaliste.numero_membre,
                "avaliste_nom": "DUPONT",
            },
            format="json",
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Voie 3 — CAMPAIGN
# ---------------------------------------------------------------------------


class TestVoieCampaign:
    def test_member_with_campaign_id_creates_lr_en_validation(self, active_member):
        _seed_fee()
        _new_member(active_member)
        c = _open_campaign()

        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "25000",
                "duree_mois": 6,
                "motif": "Test campagne",
                "campaign_id": c.id,
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["route"] == "campaign"
        assert body["loan_request"]["statut"] == "en_validation_campagne"

        lr = LoanRequest.objects.get(pk=body["loan_request"]["id"])
        assert lr.microcampaign_id == c.id

    def test_profil_cible_finds_campaign(self, active_member):
        _seed_fee()
        _new_member(active_member)
        c = _open_campaign(profil="agriculteurs")

        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "20000",
                "duree_mois": 6,
                "motif": "Test profil",
                "profil_cible": "agriculteurs",
            },
            format="json",
        )
        assert r.status_code == 201
        assert r.json()["route"] == "campaign"

    def test_amount_above_campaign_max_rejects(self, active_member):
        _seed_fee()
        _new_member(active_member)
        c = _open_campaign()  # max = 50k

        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "100000",  # > 50000
                "duree_mois": 6,
                "motif": "Test",
                "campaign_id": c.id,
            },
            format="json",
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Pré-checks universels
# ---------------------------------------------------------------------------


class TestUniversalGuards:
    def test_pending_request_blocks_any_voie(self, active_member):
        _seed_fee()
        _ancient_brc(active_member)
        _seed_savings(active_member, 50000)
        LoanRequest.objects.create(
            member=active_member,
            montant_demande=Decimal("50000"),
            duree_mois=6,
            motif="déjà en cours",
            statut=LoanRequest.Statut.EN_INSTRUCTION,
        )
        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 403
        assert any("en cours" in m.lower() for m in r.json()["motifs"])

    def test_no_route_returns_403_with_motifs(self, active_member):
        _seed_fee()
        _new_member(active_member)  # pas senior
        # Pas d'avaliste, pas de campagne → aucune voie applicable.
        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 403
        body = r.json()
        assert len(body["motifs"]) >= 1  # motif de la voie choisie (plancher apport 30 %)


# ---------------------------------------------------------------------------
# Backwards compat
# ---------------------------------------------------------------------------


class TestBackwardsCompat:
    def test_legacy_response_shape_still_has_loan_request_and_frais(
        self, active_member
    ):
        """L'ancienne UI continue de fonctionner — clés `loan_request` et
        `frais_a_payer` toujours présentes dans la réponse 201."""
        _seed_fee()
        _ancient_brc(active_member)
        _seed_classic(active_member, 100000)  # auto-couverture directe
        client = _api(active_member)
        r = client.post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 201
        body = r.json()
        assert "loan_request" in body
        assert "frais_a_payer" in body
        assert body["frais_a_payer"]["code"] == "DEMANDE_CREDIT"


class TestL5CniDemandeur:
    def test_cni_demandeur_stored_on_submit(self, active_member):
        _seed_fee()
        _new_member(active_member)
        _seed_classic(active_member, 100000)
        r = _api(active_member).post(
            "/api/v1/loans/requests/",
            {
                "montant_demande": "100000",
                "duree_mois": 6,
                "motif": "Test",
                "cni_demandeur": "CNI-DEM-123",
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        assert lr.cni_demandeur == "CNI-DEM-123"
        assert r.json()["loan_request"]["cni_demandeur"] == "CNI-DEM-123"


class TestL6StudyDeadline:
    def test_study_deadline_set_on_submit(self, active_member):
        from datetime import date as _date, timedelta as _td

        _seed_fee()
        _new_member(active_member)
        _seed_classic(active_member, 100000)
        r = _api(active_member).post(
            "/api/v1/loans/requests/",
            {"montant_demande": "100000", "duree_mois": 6, "motif": "Test"},
            format="json",
        )
        assert r.status_code == 201, r.content
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        # Défaut 30 jours après la soumission.
        assert lr.date_limite_etude == _date.today() + _td(days=30)
        assert r.json()["loan_request"]["date_limite_etude"] is not None
