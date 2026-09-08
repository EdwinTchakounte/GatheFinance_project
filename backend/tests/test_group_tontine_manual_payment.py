"""Versement MANUEL (agence) dans une tontine de groupe — saisie cash-in admin.

Beaucoup de réunions cotisent en espèces sur place. Sans ce canal, la cagnotte
ne pouvait être alimentée que par Mobile Money ou prélèvement sur épargne : le
liquide encaissé en séance restait hors système.

Ce que ces tests figent :
  - la saisie agence crédite réellement la cagnotte (et pas seulement un
    Payment orphelin) ;
  - elle applique les MÊMES barrières que le canal membre — réunion ouverte,
    membre au roster — pour qu'une saisie admin ne soit pas un contournement ;
  - elle sait rembourser un prêt de la réunion au lieu de cotiser ;
  - un échec de la règle métier ne laisse aucun Payment derrière lui.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.payments.models import Payment
from apps_coop.special_collections import group_services as gs
from apps_coop.special_collections.models import (
    GroupTontine,
    GroupTontineLoan,
    GroupTontineMember,
    GroupTontineTransaction,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/payments/admin/cash-in/"
_JAN = datetime.date(2026, 1, 1)
Role = GroupTontineMember.Role


def _admin():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m.user


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _group():
    pres = MemberFactory()
    membre = MemberFactory()
    group = gs.create_group(
        nom="Réunion Akwa",
        montant_cotisation=Decimal("5000"),
        roster=[
            {"member": pres, "role": Role.PRESIDENT},
            {"member": membre, "role": Role.MEMBRE},
        ],
    )
    return group, pres, membre


def _post(user, **payload):
    body = {"type": Payment.Type.TONTINE_GROUPE, **payload}
    return _api(user).post(URL, body, format="json")


# --- Le cas nominal ---------------------------------------------------------


class TestCotisationEspeces:
    def test_credite_la_cagnotte_et_trace_le_versement(self):
        group, _pres, membre = _group()
        solde_avant = Decimal(group.solde)

        res = _post(
            _admin(),
            member_id=membre.id,
            group_id=group.id,
            montant="5000",
            reference_externe="BORD-2026-014",
        )

        assert res.status_code == 201, res.json()
        group.refresh_from_db()
        assert Decimal(group.solde) == solde_avant + Decimal("5000")

        row = GroupTontineTransaction.objects.filter(
            group=group, member=membre,
            type_op=GroupTontineTransaction.TypeOp.COTISATION,
        ).latest("id")
        assert Decimal(row.montant) == Decimal("5000")
        # Le libellé distingue l'espèce du Mobile Money — l'audit de séance
        # doit pouvoir dire d'où vient l'argent.
        assert row.libelle == "Cotisation agence"

    def test_cree_un_payment_manuel_valide_rattache_a_la_reunion(self):
        group, _pres, membre = _group()

        _post(_admin(), member_id=membre.id, group_id=group.id, montant="5000")

        p = Payment.objects.filter(member=membre, type=Payment.Type.TONTINE_GROUPE).latest("id")
        assert p.source == Payment.Source.MANUEL
        assert p.statut == Payment.Statut.VALIDE
        # Sans cette FK, le hook ne saurait pas quelle cagnotte créditer.
        assert p.group_tontine_id == group.id
        assert p.reference_externe == "" or isinstance(p.reference_externe, str)

    def test_deux_versements_s_additionnent(self):
        group, _pres, membre = _group()
        admin = _admin()

        _post(admin, member_id=membre.id, group_id=group.id, montant="5000")
        _post(admin, member_id=membre.id, group_id=group.id, montant="3000")

        group.refresh_from_db()
        assert Decimal(group.solde) == Decimal("8000")


# --- Les barrières, identiques au canal membre ------------------------------


class TestBarrieres:
    def test_reunion_introuvable_404(self):
        _grp, _pres, membre = _group()
        res = _post(_admin(), member_id=membre.id, group_id=999999, montant="5000")
        assert res.status_code == 404
        assert "éunion introuvable" in res.json()["detail"]

    def test_reunion_cloturee_refusee(self):
        group, pres, membre = _group()
        gs.close_group(group, by=pres)

        res = _post(_admin(), member_id=membre.id, group_id=group.id, montant="5000")

        assert res.status_code == 400
        assert "clôturée" in res.json()["detail"]

    def test_membre_hors_roster_refuse(self):
        group, _pres, _membre = _group()
        etranger = MemberFactory()

        res = _post(_admin(), member_id=etranger.id, group_id=group.id, montant="5000")

        assert res.status_code == 400
        assert "ne fait pas partie" in res.json()["detail"]

    def test_group_id_absent_refuse(self):
        _grp, _pres, membre = _group()
        res = _post(_admin(), member_id=membre.id, montant="5000")
        assert res.status_code == 404

    def test_montant_negatif_refuse(self):
        group, _pres, membre = _group()
        res = _post(_admin(), member_id=membre.id, group_id=group.id, montant="-100")
        assert res.status_code == 400

    def test_un_refus_ne_laisse_aucun_payment(self):
        group, pres, membre = _group()
        gs.close_group(group, by=pres)

        _post(_admin(), member_id=membre.id, group_id=group.id, montant="5000")

        assert not Payment.objects.filter(type=Payment.Type.TONTINE_GROUPE).exists()

    def test_reserve_au_staff(self):
        group, _pres, membre = _group()
        intrus = MemberFactory()

        res = _api(intrus.user).post(
            URL,
            {
                "type": Payment.Type.TONTINE_GROUPE,
                "member_id": membre.id,
                "group_id": group.id,
                "montant": "5000",
            },
            format="json",
        )

        assert res.status_code in (401, 403)
        group.refresh_from_db()
        assert Decimal(group.solde) == Decimal("0")


# --- Remboursement d'un prêt de la réunion, en espèces ----------------------


class TestRemboursementPret:
    def _group_avec_pret(self):
        group, pres, membre = _group()
        # Cagnotte alimentée pour pouvoir prêter.
        gs.GroupTontine.objects.filter(pk=group.pk).update(solde=Decimal("50000"))
        group.refresh_from_db()
        loan, _row = gs.grant_loan(
            group=group, member=membre, montant=Decimal("20000"), by=pres
        )
        group.refresh_from_db()
        return group, pres, membre, loan

    def test_rembourse_le_pret_au_lieu_de_cotiser(self):
        group, _pres, membre, loan = self._group_avec_pret()
        du_avant = Decimal(loan.solde_restant)

        res = _post(
            _admin(),
            member_id=membre.id,
            group_id=group.id,
            group_loan_id=loan.id,
            montant="5000",
        )

        assert res.status_code == 201, res.json()
        loan.refresh_from_db()
        assert Decimal(loan.solde_restant) == du_avant - Decimal("5000")
        # Aucune cotisation parasite n'a été créée pour ce versement.
        assert not GroupTontineTransaction.objects.filter(
            group=group, member=membre,
            type_op=GroupTontineTransaction.TypeOp.COTISATION,
            libelle="Cotisation agence",
        ).exists()

    def test_pret_deja_solde_refuse(self):
        group, _pres, membre, loan = self._group_avec_pret()
        GroupTontineLoan.objects.filter(pk=loan.pk).update(
            statut=GroupTontineLoan.Statut.SOLDE
        )

        res = _post(
            _admin(), member_id=membre.id, group_id=group.id,
            group_loan_id=loan.id, montant="5000",
        )

        assert res.status_code == 400
        assert "soldé" in res.json()["detail"]

    def test_pret_d_un_autre_membre_refuse(self):
        group, pres, membre, loan = self._group_avec_pret()

        res = _post(
            _admin(), member_id=pres.id, group_id=group.id,
            group_loan_id=loan.id, montant="5000",
        )

        assert res.status_code == 404
        assert "introuvable" in res.json()["detail"]


# --- Non-régression des autres canaux ---------------------------------------


def test_les_types_cash_in_existants_restent_acceptes():
    """Garde-fou : l'ajout de TONTINE_GROUPE ne doit rien retirer."""
    from apps_coop.payments.views import _CASH_IN_ALLOWED_TYPES

    for t in (
        Payment.Type.FRAIS_ADHESION,
        Payment.Type.FRAIS_INSCRIPTION,
        Payment.Type.FRAIS_CARNET,
        Payment.Type.EPARGNE,
        Payment.Type.EPARGNE_CLASSIQUE,
        Payment.Type.CAISSE_SCOLAIRE,
        Payment.Type.TONTINE_ALIMENTAIRE,
        Payment.Type.REMBOURSEMENT,
    ):
        assert t in _CASH_IN_ALLOWED_TYPES
    assert Payment.Type.TONTINE_GROUPE in _CASH_IN_ALLOWED_TYPES
    # DECAISSEMENT n'est PAS un encaissement : il ne doit jamais y entrer.
    assert Payment.Type.DECAISSEMENT not in _CASH_IN_ALLOWED_TYPES


def test_un_versement_de_collecte_individuelle_ne_touche_pas_la_cagnotte():
    """Isolation : les deux familles de collectes ne doivent pas se mélanger."""
    group, _pres, membre = _group()

    res = _post(
        _admin(), member_id=membre.id, group_id=group.id, montant="5000",
    )
    assert res.status_code == 201

    # Aucune participation individuelle n'a été créée au passage.
    from apps_coop.special_collections.models import SpecialCollectionMembership

    assert not SpecialCollectionMembership.objects.filter(member=membre).exists()
    assert GroupTontine.objects.get(pk=group.pk).solde == Decimal("5000")
