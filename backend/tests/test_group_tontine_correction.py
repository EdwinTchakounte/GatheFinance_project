"""Correction d'un montant de sortie saisi par erreur au guichet.

Un agent se trompe de montant en versant au bénéficiaire ou en accordant un
prêt. Jusqu'ici rien ne permettait de le rattraper : il fallait vivre avec
l'erreur, ou bricoler en base.

Approche retenue — la même que pour les saisies antidatées de l'épargne : le
registre reste **append-only**. L'écriture fautive n'est jamais réécrite ; elle
est marquée corrigée, et une écriture d'AJUSTEMENT porte l'écart. Un contrôleur
voit donc l'erreur ET sa correction, jamais une histoire réécrite.

Ce que ces tests figent :
  - la cagnotte, l'épargne et la dette suivent l'écart, dans les deux sens ;
  - un versement ESPÈCES ne touche pas l'épargne, un versement ÉPARGNE si —
    c'est la destination ENREGISTRÉE qui décide, jamais le libellé texte ;
  - une écriture sans destination connue est REFUSÉE plutôt que devinée ;
  - on ne corrige pas deux fois, ni une écriture adossée à un paiement.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AuditLog
from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.special_collections import group_services as gs
from apps_coop.special_collections.models import (
    GroupTontine,
    GroupTontineLoan,
    GroupTontineMember,
    GroupTontineTransaction,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

_JAN = datetime.date(2026, 1, 1)
Role = GroupTontineMember.Role
TypeOp = GroupTontineTransaction.TypeOp


def _staff():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m.user


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _groupe(solde="50000"):
    pres, benef = MemberFactory(), MemberFactory()
    group = gs.create_group(
        nom="Réunion Akwa", montant_cotisation=Decimal("5000"),
        roster=[
            {"member": pres, "role": Role.PRESIDENT},
            {"member": benef, "role": Role.MEMBRE},
        ],
    )
    GroupTontine.objects.filter(pk=group.pk).update(solde=Decimal(solde))
    group.refresh_from_db()
    return group, pres, benef


def _versement(group, benef, montant, destination, by=None):
    return gs.payout_beneficiary(
        group=group, beneficiary=benef, montant=Decimal(montant),
        by=by or _staff(), destination=destination, skip_perm_check=True,
    )


def _url(group) -> str:
    return f"/api/v1/special-collections/admin/groups/{group.pk}/correct-amount/"


# --- La correction suit l'écart, dans les deux sens -------------------------


class TestEcart:
    def test_baisse_restitue_la_cagnotte(self):
        """20 000 saisis au lieu de 5 000 : 15 000 reviennent dans la cagnotte."""
        group, _pres, benef = _groupe("50000")
        tx = _versement(group, benef, "20000", "cash")
        group.refresh_from_db()
        assert group.solde == Decimal("30000")

        gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("5000"),
            motif="Erreur de saisie en séance", by=_staff(),
        )

        group.refresh_from_db()
        assert group.solde == Decimal("45000")

    def test_hausse_creuse_la_cagnotte(self):
        group, _pres, benef = _groupe("50000")
        tx = _versement(group, benef, "5000", "cash")

        gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("12000"),
            motif="Montant sous-évalué", by=_staff(),
        )

        group.refresh_from_db()
        assert group.solde == Decimal("38000")

    def test_hausse_refusee_si_la_cagnotte_ne_suit_pas(self):
        group, _pres, benef = _groupe("10000")
        tx = _versement(group, benef, "8000", "cash")

        with pytest.raises(gs.GroupTontineError, match="insuffisante"):
            gs.corriger_montant(
                transaction=tx, nouveau_montant=Decimal("50000"),
                motif="Trop gros", by=_staff(),
            )

        group.refresh_from_db()
        assert group.solde == Decimal("2000"), "aucun mouvement partiel"


# --- La destination ENREGISTRÉE décide de ce qu'on défait -------------------


class TestDestination:
    def test_versement_especes_ne_touche_pas_lepargne(self):
        group, _pres, benef = _groupe()
        acc = ClassicSavingsAccount.objects.create(
            member=benef, solde=Decimal("1000"), date_ouverture=_JAN,
        )
        tx = _versement(group, benef, "20000", "cash")

        gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("5000"),
            motif="Correction", by=_staff(),
        )

        acc.refresh_from_db()
        assert acc.solde == Decimal("1000"), "rien n'avait été crédité"

    def test_versement_epargne_reprend_le_trop_percu(self):
        group, _pres, benef = _groupe()
        acc = ClassicSavingsAccount.objects.create(
            member=benef, solde=Decimal("0"), date_ouverture=_JAN,
        )
        tx = _versement(group, benef, "20000", "epargne")
        acc.refresh_from_db()
        assert acc.solde == Decimal("20000")

        gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("5000"),
            motif="Correction", by=_staff(),
        )

        acc.refresh_from_db()
        assert acc.solde == Decimal("5000")

    def test_epargne_negative_toleree_mais_signalee(self):
        """Le membre a déjà dépensé : un registre faux serait pire qu'un solde
        négatif visible, qui se régularise au versement suivant."""
        group, _pres, benef = _groupe()
        ClassicSavingsAccount.objects.create(
            member=benef, solde=Decimal("0"), date_ouverture=_JAN,
        )
        tx = _versement(group, benef, "20000", "epargne")
        ClassicSavingsAccount.objects.filter(member=benef).update(solde=Decimal("0"))

        res = gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("5000"),
            motif="Correction", by=_staff(),
        )

        assert res["epargne_negative"] is True
        assert ClassicSavingsAccount.objects.get(member=benef).solde == Decimal("-15000")

    def test_ecriture_sans_destination_refusee(self):
        """Antérieure à 2026-09 : on ne devine pas où l'argent est allé."""
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")
        GroupTontineTransaction.objects.filter(pk=tx.pk).update(destination="")
        tx.refresh_from_db()

        with pytest.raises(gs.GroupTontineError, match="destination"):
            gs.corriger_montant(
                transaction=tx, nouveau_montant=Decimal("5000"),
                motif="Correction", by=_staff(),
            )


# --- La dette d'un prêt suit le montant réellement remis --------------------


def test_corriger_un_pret_ajuste_la_dette():
    group, pres, emprunteur = _groupe("50000")
    loan, tx = gs.grant_loan(
        group=group, member=emprunteur, montant=Decimal("20000"),
        by=pres, destination="cash", skip_perm_check=True,
    )

    gs.corriger_montant(
        transaction=tx, nouveau_montant=Decimal("8000"),
        motif="Montant remis inférieur", by=_staff(),
    )

    loan.refresh_from_db()
    assert Decimal(loan.montant) == Decimal("8000")
    assert Decimal(loan.solde_restant) == Decimal("8000"), (
        "le membre ne doit pas rembourser ce qu'il n'a pas reçu"
    )


# --- Le registre reste append-only ------------------------------------------


class TestRegistreAppendOnly:
    def test_lecriture_dorigine_est_conservee_et_marquee(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")
        agent = _staff()

        gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("5000"),
            motif="Erreur de frappe", by=agent,
        )

        tx.refresh_from_db()
        # Le montant fautif reste lisible : on ne réécrit pas l'histoire.
        assert Decimal(tx.montant) == Decimal("20000")
        assert tx.is_corrected
        assert tx.correction_note == "Erreur de frappe"
        assert tx.corrected_by_id == agent.id

    def test_une_ecriture_dajustement_porte_lecart(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")

        gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("5000"),
            motif="Erreur de frappe", by=_staff(),
        )

        ajust = GroupTontineTransaction.objects.filter(
            group=group, type_op=TypeOp.AJUSTEMENT,
        ).latest("id")
        assert Decimal(ajust.montant) == Decimal("15000")
        assert "20000 → 5000" in ajust.libelle

    def test_audit_trace_lecart_et_le_motif(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")

        gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("5000"),
            motif="Erreur de frappe", by=_staff(),
        )

        log = AuditLog.objects.filter(action="group_tontine.montant_corrige").latest("id")
        # On compare des montants, pas leur représentation textuelle.
        assert Decimal(log.details_json["ancien"]) == Decimal("20000")
        assert Decimal(log.details_json["nouveau"]) == Decimal("5000")
        assert Decimal(log.details_json["ecart"]) == Decimal("-15000")
        assert log.details_json["motif"] == "Erreur de frappe"


# --- Les refus --------------------------------------------------------------


class TestRefus:
    def test_pas_deux_corrections_sur_la_meme_ecriture(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")
        gs.corriger_montant(
            transaction=tx, nouveau_montant=Decimal("5000"), motif="1re", by=_staff(),
        )
        tx.refresh_from_db()

        with pytest.raises(gs.GroupTontineError, match="déjà été corrigée"):
            gs.corriger_montant(
                transaction=tx, nouveau_montant=Decimal("3000"), motif="2e", by=_staff(),
            )

    def test_motif_obligatoire(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")

        with pytest.raises(gs.GroupTontineError, match="motif"):
            gs.corriger_montant(
                transaction=tx, nouveau_montant=Decimal("5000"), motif="  ", by=_staff(),
            )

    def test_montant_identique_refuse(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")

        with pytest.raises(gs.GroupTontineError, match="déjà celui-ci"):
            gs.corriger_montant(
                transaction=tx, nouveau_montant=Decimal("20000"),
                motif="Rien", by=_staff(),
            )

    def test_une_cotisation_nest_pas_corrigible_ici(self):
        """Adossée à un paiement : la corriger ici ferait diverger la caisse."""
        group, _pres, benef = _groupe()
        tx = gs._apply_cotisation(
            group=group, member=benef, montant=Decimal("5000"), is_manual=True,
        )

        with pytest.raises(gs.GroupTontineError, match="sorties de cagnotte"):
            gs.corriger_montant(
                transaction=tx, nouveau_montant=Decimal("3000"),
                motif="Correction", by=_staff(),
            )

    def test_reunion_cloturee_figee(self):
        group, pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")
        gs.close_group(group, by=pres)

        with pytest.raises(gs.GroupTontineError, match="clôturée"):
            gs.corriger_montant(
                transaction=tx, nouveau_montant=Decimal("5000"),
                motif="Correction", by=_staff(),
            )


# --- Endpoint ---------------------------------------------------------------


class TestEndpoint:
    def test_staff_peut_corriger(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")

        res = _api(_staff()).post(
            _url(group),
            {"transaction_id": tx.id, "montant": "5000", "motif": "Erreur"},
            format="json",
        )

        assert res.status_code == 200, res.json()
        assert Decimal(res.json()["correction"]["ecart"]) == Decimal("-15000")
        group.refresh_from_db()
        assert group.solde == Decimal("45000")

    def test_motif_manquant_renvoie_400(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")

        res = _api(_staff()).post(
            _url(group), {"transaction_id": tx.id, "montant": "5000"}, format="json",
        )

        assert res.status_code == 400
        assert "motif" in res.json()["detail"]

    def test_ecriture_dune_autre_reunion_introuvable(self):
        """Le scoping empêche de corriger l'écriture d'un autre groupe."""
        group_a, _p, benef_a = _groupe()
        group_b, _p2, _b2 = _groupe()
        tx_a = _versement(group_a, benef_a, "20000", "cash")

        res = _api(_staff()).post(
            f"/api/v1/special-collections/admin/groups/{group_b.pk}/correct-amount/",
            {"transaction_id": tx_a.id, "montant": "5000", "motif": "X"},
            format="json",
        )

        assert res.status_code == 404

    def test_reserve_au_staff(self):
        group, _pres, benef = _groupe()
        tx = _versement(group, benef, "20000", "cash")
        intrus = MemberFactory()

        res = _api(intrus.user).post(
            _url(group),
            {"transaction_id": tx.id, "montant": "5000", "motif": "X"},
            format="json",
        )

        assert res.status_code in (401, 403)
        group.refresh_from_db()
        assert group.solde == Decimal("30000"), "inchangée"
