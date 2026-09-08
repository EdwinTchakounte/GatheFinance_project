"""Retraits manuels (agence) sur les collectes particulières + frais de carnet.

Deux manques comblés côté « débit manuel » :

  1. les comptes ``tontine`` / ``caisse`` n'y étaient pas — leur décaissement
     n'existait que sur l'écran collectes, alors que c'est le même geste de
     caisse que pour la collecte journalière ou l'épargne classique ;
  2. les frais de carnet tontine/caisse n'étaient pas prélevables depuis
     l'épargne, alors que le carnet est OBLIGATOIRE pour verser.

Ce que ces tests figent :
  - le débit passe par ``decaisser_participation`` (mêmes règles, pas de
    logique d'argent dupliquée) ;
  - l'ambiguïté sur la collecte visée est REFUSÉE, jamais devinée ;
  - les comptes historiques (colonne ``type`` vide) restent atteignables ;
  - les comptes existants (collecte / classique) ne bougent pas.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps_coop.audit.models import AuditLog
from apps_coop.payments.manual_debit_services import ManualDebitError, manual_debit
from apps_coop.payments.models import FeeType, Payment
from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.special_collections.models import (
    SpecialCollectionCycle,
    SpecialCollectionMembership,
    SpecialCollectionTransaction,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

_JAN = date(2026, 1, 1)


def _cycle(type_="caisse_scolaire", nom="Caisse 2026", debut=_JAN):
    return SpecialCollectionCycle.objects.create(
        type=type_, nom=nom, montant_minimal=Decimal("1000"), date_debut=debut,
    )


def _participation(member, cycle, solde="50000", type_=None):
    return SpecialCollectionMembership.objects.create(
        member=member,
        cycle=cycle,
        # `type_=None` reproduit les lignes historiques où la colonne
        # dénormalisée n'a jamais été renseignée.
        type=type_ if type_ is not None else "",
        statut=SpecialCollectionMembership.Statut.VALIDE,
        solde=Decimal(solde),
    )


def _classic(member, solde="0"):
    return ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(solde), date_ouverture=_JAN,
    )


# --- Retrait sur une collecte particulière ----------------------------------


class TestRetraitCollecte:
    def test_caisse_scolaire_en_especes_debite_le_solde(self):
        member = MemberFactory()
        cycle = _cycle()
        part = _participation(member, cycle, "50000")

        res = manual_debit(
            member=member, compte="caisse", montant="20000",
            motif="Retrait agence", cycle_id=cycle.id,
        )

        part.refresh_from_db()
        assert part.solde == Decimal("30000")
        assert res["compte"] == "caisse"
        assert res["destination"] == "cash"
        assert Decimal(res["solde_apres"]) == Decimal("30000")

    def test_tontine_alimentaire_debite_aussi(self):
        member = MemberFactory()
        cycle = _cycle("tontine_alimentaire", "Tontine 2026")
        part = _participation(member, cycle, "12000")

        manual_debit(member=member, compte="tontine", montant="5000", cycle_id=cycle.id)

        part.refresh_from_db()
        assert part.solde == Decimal("7000")

    def test_destination_epargne_bascule_vers_lepargne_classique(self):
        member = MemberFactory()
        cycle = _cycle()
        part = _participation(member, cycle, "40000")
        acc = _classic(member, "1000")

        manual_debit(
            member=member, compte="caisse", montant="15000",
            cycle_id=cycle.id, destination="epargne",
        )

        part.refresh_from_db()
        acc.refresh_from_db()
        assert part.solde == Decimal("25000")
        assert acc.solde == Decimal("16000"), "l'argent doit ARRIVER quelque part"

    def test_ecriture_retrait_tracee_sur_la_collecte(self):
        member = MemberFactory()
        cycle = _cycle()
        part = _participation(member, cycle, "9000")

        manual_debit(member=member, compte="caisse", montant="4000", cycle_id=cycle.id)

        row = SpecialCollectionTransaction.objects.filter(membership=part).latest("id")
        assert row.type_op == SpecialCollectionTransaction.TypeOp.RETRAIT
        assert Decimal(row.montant) == Decimal("4000")
        assert Decimal(row.solde_apres) == Decimal("5000")

    def test_audit_ecrit_avec_le_compte_et_la_collecte(self):
        member = MemberFactory()
        cycle = _cycle()
        _participation(member, cycle, "9000")

        manual_debit(member=member, compte="caisse", montant="4000", cycle_id=cycle.id)

        log = AuditLog.objects.filter(action="savings.manual_debit").latest("id")
        assert log.details_json["compte"] == "caisse"
        assert log.details_json["cycle_id"] == cycle.id
        assert log.details_json["destination"] == "cash"


# --- Résolution de la collecte : jamais deviner -----------------------------


class TestResolutionCollecte:
    def test_sans_cycle_id_une_seule_collecte_est_resolue(self):
        member = MemberFactory()
        cycle = _cycle()
        part = _participation(member, cycle, "8000")

        res = manual_debit(member=member, compte="caisse", montant="3000")

        part.refresh_from_db()
        assert part.solde == Decimal("5000")
        assert res["cycle_id"] == cycle.id

    def test_plusieurs_collectes_approvisionnees_refusees(self):
        """Deviner reviendrait à débiter la mauvaise caisse."""
        member = MemberFactory()
        c1 = _cycle(nom="Caisse 2025", debut=date(2025, 1, 1))
        c2 = _cycle(nom="Caisse 2026", debut=_JAN)
        _participation(member, c1, "5000")
        _participation(member, c2, "7000")

        with pytest.raises(ManualDebitError, match="précise laquelle"):
            manual_debit(member=member, compte="caisse", montant="1000")

    def test_aucune_collecte_approvisionnee_refusee(self):
        member = MemberFactory()
        _participation(member, _cycle(), "0")

        with pytest.raises(ManualDebitError, match="Aucune participation"):
            manual_debit(member=member, compte="caisse", montant="1000")

    def test_ne_confond_pas_tontine_et_caisse(self):
        member = MemberFactory()
        caisse = _cycle("caisse_scolaire", "Caisse")
        _participation(member, caisse, "5000")

        # Aucune tontine approvisionnée : on ne doit pas retomber sur la caisse.
        with pytest.raises(ManualDebitError, match="Aucune participation"):
            manual_debit(member=member, compte="tontine", montant="1000")

    def test_ligne_historique_sans_type_reste_atteignable(self):
        """La colonne `type` de la participation peut être vide sur d'anciennes
        lignes ; c'est le cycle qui fait foi."""
        member = MemberFactory()
        cycle = _cycle("tontine_alimentaire", "Tontine ancienne")
        part = _participation(member, cycle, "6000", type_="")

        manual_debit(member=member, compte="tontine", montant="2000")

        part.refresh_from_db()
        assert part.solde == Decimal("4000")


# --- Garde-fous sur l'argent ------------------------------------------------


class TestGardeFous:
    def test_montant_superieur_au_solde_refuse(self):
        member = MemberFactory()
        cycle = _cycle()
        part = _participation(member, cycle, "3000")

        with pytest.raises(ManualDebitError, match="supérieur au solde"):
            manual_debit(member=member, compte="caisse", montant="5000", cycle_id=cycle.id)

        part.refresh_from_db()
        assert part.solde == Decimal("3000"), "aucun débit partiel"

    def test_montant_nul_ou_negatif_refuse(self):
        member = MemberFactory()
        cycle = _cycle()
        _participation(member, cycle, "3000")

        for mauvais in ("0", "-500"):
            with pytest.raises(ManualDebitError):
                manual_debit(
                    member=member, compte="caisse", montant=mauvais, cycle_id=cycle.id,
                )

    def test_destination_inconnue_refusee(self):
        member = MemberFactory()
        cycle = _cycle()
        _participation(member, cycle, "3000")

        with pytest.raises(ManualDebitError, match="Destination"):
            manual_debit(
                member=member, compte="caisse", montant="1000",
                cycle_id=cycle.id, destination="bitcoin",
            )

    def test_compte_inconnu_mentionne_les_quatre_comptes(self):
        member = MemberFactory()
        with pytest.raises(ManualDebitError, match="tontine"):
            manual_debit(member=member, compte="livret-a", montant="1000")


# --- Frais de carnet tontine / caisse prélevés sur l'épargne ----------------


class TestFraisCarnet:
    def _fee(self, code, montant="1500"):
        return FeeType.objects.update_or_create(
            code=code,
            defaults={"libelle": f"Frais {code}", "montant": Decimal(montant), "actif": True},
        )[0]

    def test_carnet_tontine_prelevable_depuis_lepargne(self):
        member = MemberFactory()
        acc = _classic(member, "20000")
        self._fee(FeeType.Code.CARNET_TONTINE, "1500")

        res = manual_debit(member=member, fee_code=FeeType.Code.CARNET_TONTINE)

        acc.refresh_from_db()
        assert acc.solde == Decimal("18500")
        p = Payment.objects.get(pk=res["payment_id"])
        assert p.type == Payment.Type.FRAIS_CARNET_TONTINE
        assert p.source == Payment.Source.DEDUCTION_EPARGNE
        assert p.statut == Payment.Statut.VALIDE

    def test_carnet_caisse_prelevable_depuis_lepargne(self):
        member = MemberFactory()
        acc = _classic(member, "20000")
        self._fee(FeeType.Code.CARNET_CAISSE, "2000")

        res = manual_debit(member=member, fee_code=FeeType.Code.CARNET_CAISSE)

        acc.refresh_from_db()
        assert acc.solde == Decimal("18000")
        assert Payment.objects.get(pk=res["payment_id"]).type == (
            Payment.Type.FRAIS_CARNET_CAISSE
        )

    def test_le_tarif_du_bareme_prime_sur_le_montant_saisi(self):
        """Un frais est au tarif officiel : la saisie ne doit pas le contourner."""
        member = MemberFactory()
        acc = _classic(member, "20000")
        self._fee(FeeType.Code.CARNET_TONTINE, "1500")

        manual_debit(member=member, fee_code=FeeType.Code.CARNET_TONTINE, montant="10")

        acc.refresh_from_db()
        assert acc.solde == Decimal("18500")

    def test_epargne_insuffisante_refusee(self):
        member = MemberFactory()
        acc = _classic(member, "500")
        self._fee(FeeType.Code.CARNET_TONTINE, "1500")

        with pytest.raises(ManualDebitError, match="insuffisant"):
            manual_debit(member=member, fee_code=FeeType.Code.CARNET_TONTINE)

        acc.refresh_from_db()
        assert acc.solde == Decimal("500")


# --- Non-régression des comptes existants -----------------------------------


class TestNonRegression:
    def test_retrait_epargne_classique_inchange(self):
        member = MemberFactory()
        acc = _classic(member, "10000")

        res = manual_debit(member=member, compte="classique", montant="4000", motif="test")

        acc.refresh_from_db()
        assert acc.solde == Decimal("6000")
        assert res["compte"] == "classique"
        # Le retour des comptes simples ne porte PAS les clés collectes.
        assert "cycle_id" not in res

    def test_les_frais_historiques_restent_prelevables(self):
        from apps_coop.payments.manual_debit_services import _FEE_CODE_TO_TYPE

        for code in (
            FeeType.Code.INSCRIPTION,
            FeeType.Code.ADHESION,
            FeeType.Code.CARNET,
            FeeType.Code.RECONDUCTION,
        ):
            assert code in _FEE_CODE_TO_TYPE
        assert FeeType.Code.CARNET_TONTINE in _FEE_CODE_TO_TYPE
        assert FeeType.Code.CARNET_CAISSE in _FEE_CODE_TO_TYPE
        # DEMANDE_CREDIT n'est pas réglable par ce canal (frais d'étude : flow
        # dédié) — l'ajout ne doit pas l'avoir ouvert par effet de bord.
        assert FeeType.Code.DEMANDE_CREDIT not in _FEE_CODE_TO_TYPE
