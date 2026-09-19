"""Sortie de cagnotte enregistrée au GUICHET (versement au bénéficiaire).

L'argent des réunions est détenu par la coopérative : le cash-in agence existait
déjà, mais rien ne permettait d'enregistrer la SORTIE depuis le guichet. Une
réunion dont le trésorier était absent, sans téléphone — ou qui n'en avait tout
simplement pas — restait bloquée : personne ne pouvait servir le bénéficiaire.

Second manque comblé : le versement atterrissait TOUJOURS sur l'épargne
classique. Or une tontine se solde le plus souvent en billets à la fin de la
séance ; forcer ce cas dans l'épargne obligeait le bénéficiaire à déposer une
demande de retrait pour ressortir son propre argent, et gonflait artificiellement
les soldes d'épargne — donc les états financiers.

Ce que ces tests figent :
  - le guichet peut servir un bénéficiaire même sans trésorier au roster ;
  - les deux modalités (espèces / épargne) débitent la cagnotte de la même
    façon, mais une seule crédite l'épargne ;
  - les garde-fous métier restent (cagnotte insuffisante, réunion close,
    bénéficiaire hors roster) ;
  - le canal membre garde son contrôle de droit — l'ouverture agence ne doit
    pas l'avoir affaibli.
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
    GroupTontineMember,
    GroupTontineTransaction,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

_JAN = datetime.date(2026, 1, 1)
Role = GroupTontineMember.Role


def _url(group) -> str:
    return f"/api/v1/special-collections/admin/groups/{group.pk}/payout/"


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


def _groupe(*, avec_tresorier=True, solde="50000"):
    """Réunion approvisionnée. `avec_tresorier=False` reproduit le cas réel
    d'une réunion qui n'a personne pour gérer les fonds."""
    pres = MemberFactory()
    benef = MemberFactory()
    roster = [
        {"member": pres, "role": Role.PRESIDENT},
        {"member": benef, "role": Role.MEMBRE},
    ]
    if avec_tresorier:
        roster.insert(1, {"member": MemberFactory(), "role": Role.TRESORIER})
    group = gs.create_group(
        nom="Réunion Bonabéri", montant_cotisation=Decimal("5000"), roster=roster,
    )
    GroupTontine.objects.filter(pk=group.pk).update(solde=Decimal(solde))
    group.refresh_from_db()
    return group, pres, benef


# --- Le guichet peut servir le bénéficiaire ---------------------------------


class TestVersementAgence:
    def test_especes_debite_la_cagnotte_sans_crediter_lepargne(self):
        group, _pres, benef = _groupe()
        acc = ClassicSavingsAccount.objects.create(
            member=benef, solde=Decimal("1000"), date_ouverture=_JAN,
        )

        res = _api(_staff()).post(
            _url(group),
            {"member_id": benef.id, "montant": "20000", "destination": "cash"},
            format="json",
        )

        assert res.status_code == 200, res.json()
        group.refresh_from_db()
        acc.refresh_from_db()
        assert group.solde == Decimal("30000"), "la cagnotte doit être débitée"
        # L'argent est sorti de la coopérative : rien n'est crédité en interne.
        assert acc.solde == Decimal("1000")

    def test_epargne_debite_la_cagnotte_et_credite_le_beneficiaire(self):
        group, _pres, benef = _groupe()
        acc = ClassicSavingsAccount.objects.create(
            member=benef, solde=Decimal("1000"), date_ouverture=_JAN,
        )

        res = _api(_staff()).post(
            _url(group),
            {"member_id": benef.id, "montant": "20000", "destination": "epargne"},
            format="json",
        )

        assert res.status_code == 200, res.json()
        group.refresh_from_db()
        acc.refresh_from_db()
        assert group.solde == Decimal("30000")
        assert acc.solde == Decimal("21000"), "l'argent doit ARRIVER quelque part"

    def test_especes_par_defaut(self):
        """Le cas courant en séance : le bénéficiaire repart avec les billets."""
        group, _pres, benef = _groupe()
        acc = ClassicSavingsAccount.objects.create(
            member=benef, solde=Decimal("0"), date_ouverture=_JAN,
        )

        _api(_staff()).post(
            _url(group), {"member_id": benef.id, "montant": "10000"}, format="json",
        )

        acc.refresh_from_db()
        assert acc.solde == Decimal("0")

    def test_sert_meme_une_reunion_SANS_tresorier(self):
        """Le cœur du besoin : certaines réunions n'ont personne pour gérer."""
        group, _pres, benef = _groupe(avec_tresorier=False)

        res = _api(_staff()).post(
            _url(group), {"member_id": benef.id, "montant": "15000"}, format="json",
        )

        assert res.status_code == 200, res.json()
        group.refresh_from_db()
        assert group.solde == Decimal("35000")

    def test_ecriture_tracee_avec_la_modalite(self):
        group, _pres, benef = _groupe()

        _api(_staff()).post(
            _url(group),
            {"member_id": benef.id, "montant": "5000", "destination": "cash"},
            format="json",
        )

        row = GroupTontineTransaction.objects.filter(
            group=group, type_op=GroupTontineTransaction.TypeOp.VERSEMENT_BENEFICIAIRE,
        ).latest("id")
        assert row.member_id == benef.id
        assert Decimal(row.montant) == Decimal("5000")
        # Un contrôleur doit pouvoir dire, des mois après, où l'argent est parti.
        assert "espèces" in row.libelle

    def test_audit_distingue_le_canal_et_la_destination(self):
        group, _pres, benef = _groupe()
        agent = _staff()

        _api(agent).post(
            _url(group),
            {"member_id": benef.id, "montant": "5000", "destination": "cash"},
            format="json",
        )

        log = AuditLog.objects.filter(action="group_tontine.payout").latest("id")
        assert log.details_json["destination"] == "cash"
        assert log.details_json["canal"] == "agence"
        assert log.details_json["beneficiary_id"] == benef.id


# --- Les garde-fous métier tiennent -----------------------------------------


class TestGardeFous:
    def test_cagnotte_insuffisante_refusee(self):
        group, _pres, benef = _groupe(solde="3000")

        res = _api(_staff()).post(
            _url(group), {"member_id": benef.id, "montant": "10000"}, format="json",
        )

        assert res.status_code == 400
        assert "insuffisante" in res.json()["detail"]
        group.refresh_from_db()
        assert group.solde == Decimal("3000"), "aucun débit partiel"

    def test_reunion_cloturee_refusee(self):
        group, pres, benef = _groupe()
        gs.close_group(group, by=pres)

        res = _api(_staff()).post(
            _url(group), {"member_id": benef.id, "montant": "5000"}, format="json",
        )

        assert res.status_code == 400
        assert "clôturée" in res.json()["detail"]

    def test_beneficiaire_hors_roster_refuse(self):
        group, _pres, _benef = _groupe()
        etranger = MemberFactory()

        res = _api(_staff()).post(
            _url(group), {"member_id": etranger.id, "montant": "5000"}, format="json",
        )

        assert res.status_code == 400
        assert "membre de la réunion" in res.json()["detail"]

    def test_montant_invalide_refuse(self):
        group, _pres, benef = _groupe()
        for mauvais in ("0", "-5000"):
            res = _api(_staff()).post(
                _url(group), {"member_id": benef.id, "montant": mauvais}, format="json",
            )
            assert res.status_code == 400

    def test_destination_inconnue_refusee(self):
        group, _pres, benef = _groupe()

        res = _api(_staff()).post(
            _url(group),
            {"member_id": benef.id, "montant": "5000", "destination": "bitcoin"},
            format="json",
        )

        assert res.status_code == 400
        assert "Destination" in res.json()["detail"]

    def test_reserve_au_staff(self):
        group, _pres, benef = _groupe()
        intrus = MemberFactory()

        res = _api(intrus.user).post(
            _url(group), {"member_id": benef.id, "montant": "5000"}, format="json",
        )

        assert res.status_code in (401, 403)
        group.refresh_from_db()
        assert group.solde == Decimal("50000")


# --- Non-régression du canal membre -----------------------------------------


class TestCanalMembreIntact:
    def test_un_simple_membre_ne_peut_toujours_pas_verser(self):
        """L'ouverture agence ne doit PAS avoir affaibli le contrôle de droit."""
        group, _pres, benef = _groupe()

        with pytest.raises(gs.GroupTontineError, match="autorisation"):
            gs.payout_beneficiary(
                group=group, beneficiary=benef, montant=Decimal("5000"), by=benef,
            )

    def test_le_president_verse_toujours_vers_lepargne_par_defaut(self):
        """Comportement historique du canal membre : inchangé."""
        group, pres, benef = _groupe()
        acc = ClassicSavingsAccount.objects.create(
            member=benef, solde=Decimal("0"), date_ouverture=_JAN,
        )

        gs.payout_beneficiary(
            group=group, beneficiary=benef, montant=Decimal("5000"), by=pres,
        )

        acc.refresh_from_db()
        assert acc.solde == Decimal("5000")


# --- Prêt accordé au GUICHET ------------------------------------------------
#
# Même raison que le versement : la cooperative detient les fonds, et une
# reunion peut n'avoir personne pour engager la cagnotte.


def _url_loan(group) -> str:
    return f"/api/v1/special-collections/admin/groups/{group.pk}/loan/"


class TestPretAgence:
    def test_especes_debite_la_cagnotte_sans_crediter_lepargne(self):
        group, _pres, emprunteur = _groupe()
        acc = ClassicSavingsAccount.objects.create(
            member=emprunteur, solde=Decimal("0"), date_ouverture=_JAN,
        )

        res = _api(_staff()).post(
            _url_loan(group),
            {"member_id": emprunteur.id, "montant": "20000", "destination": "cash"},
            format="json",
        )

        assert res.status_code == 200, res.json()
        group.refresh_from_db()
        acc.refresh_from_db()
        assert group.solde == Decimal("30000")
        assert acc.solde == Decimal("0"), "les billets sont remis, rien en interne"

    def test_la_dette_est_la_meme_quelle_que_soit_la_modalite(self):
        """Le canal de remise ne doit RIEN changer à ce que le membre doit."""
        from apps_coop.special_collections.models import GroupTontineLoan

        for dest in ("cash", "epargne"):
            group, _pres, emprunteur = _groupe()
            _api(_staff()).post(
                _url_loan(group),
                {"member_id": emprunteur.id, "montant": "10000", "destination": dest},
                format="json",
            )
            pret = GroupTontineLoan.objects.filter(group=group).latest("id")
            assert Decimal(pret.montant) == Decimal("10000")
            assert Decimal(pret.solde_restant) == Decimal("10000")

    def test_sert_meme_une_reunion_SANS_tresorier(self):
        group, _pres, emprunteur = _groupe(avec_tresorier=False)

        res = _api(_staff()).post(
            _url_loan(group), {"member_id": emprunteur.id, "montant": "15000"},
            format="json",
        )

        assert res.status_code == 200, res.json()
        group.refresh_from_db()
        assert group.solde == Decimal("35000")

    def test_cagnotte_insuffisante_refusee_sans_debit(self):
        group, _pres, emprunteur = _groupe(solde="3000")

        res = _api(_staff()).post(
            _url_loan(group), {"member_id": emprunteur.id, "montant": "10000"},
            format="json",
        )

        assert res.status_code == 400
        group.refresh_from_db()
        assert group.solde == Decimal("3000")

    def test_emprunteur_hors_roster_refuse(self):
        group, _pres, _b = _groupe()
        etranger = MemberFactory()

        res = _api(_staff()).post(
            _url_loan(group), {"member_id": etranger.id, "montant": "5000"},
            format="json",
        )

        assert res.status_code == 400

    def test_reserve_au_staff(self):
        group, _pres, emprunteur = _groupe()
        intrus = MemberFactory()

        res = _api(intrus.user).post(
            _url_loan(group), {"member_id": emprunteur.id, "montant": "5000"},
            format="json",
        )

        assert res.status_code in (401, 403)


# --- Le trésorier ne prête plus ---------------------------------------------
#
# Il DÉSIGNE le bénéficiaire, il n'ENGAGE PAS la cagnotte sur une dette.
# Décision 2026-09 : engager la cagnotte revient au président ou au guichet.


class TestTresorierRestreint:
    def _reunion_avec_tresorier(self):
        pres, tres, emprunteur = MemberFactory(), MemberFactory(), MemberFactory()
        group = gs.create_group(
            nom="Réunion Deido", montant_cotisation=Decimal("5000"),
            roster=[
                {"member": pres, "role": Role.PRESIDENT},
                {"member": tres, "role": Role.TRESORIER},
                {"member": emprunteur, "role": Role.MEMBRE},
            ],
        )
        GroupTontine.objects.filter(pk=group.pk).update(solde=Decimal("50000"))
        group.refresh_from_db()
        return group, pres, tres, emprunteur

    def test_le_tresorier_ne_peut_plus_accorder_de_pret(self):
        group, _pres, tres, emprunteur = self._reunion_avec_tresorier()

        with pytest.raises(gs.GroupTontineError, match="autorisation"):
            gs.grant_loan(
                group=group, member=emprunteur, montant=Decimal("5000"), by=tres,
            )

        group.refresh_from_db()
        assert group.solde == Decimal("50000"), "aucun débit"

    def test_le_tresorier_garde_la_designation_du_beneficiaire(self):
        """Son rôle réel : dire QUI reçoit."""
        group, _pres, tres, benef = self._reunion_avec_tresorier()

        gs.payout_beneficiary(
            group=group, beneficiary=benef, montant=Decimal("5000"), by=tres,
        )

        group.refresh_from_db()
        assert group.solde == Decimal("45000")

    def test_le_president_prete_toujours(self):
        group, pres, _tres, emprunteur = self._reunion_avec_tresorier()

        gs.grant_loan(
            group=group, member=emprunteur, montant=Decimal("5000"), by=pres,
        )

        group.refresh_from_db()
        assert group.solde == Decimal("45000")

    def test_un_role_personnalise_peut_le_lui_rendre(self):
        """L'exception reste possible, mais elle devient EXPLICITE."""
        group, pres, tres, emprunteur = self._reunion_avec_tresorier()
        role = gs.create_custom_role(
            group, "Trésorier prêteur", {"can_grant_loan": True}, by=pres,
        )
        gs.assign_custom_role(group, tres, role, by=pres)

        gs.grant_loan(
            group=group, member=emprunteur, montant=Decimal("5000"), by=tres,
        )

        group.refresh_from_db()
        assert group.solde == Decimal("45000")

    def test_les_autres_droits_du_tresorier_sont_intacts(self):
        group, _pres, tres, _e = self._reunion_avec_tresorier()

        perms = gs.member_permissions(group, tres)

        assert perms["can_manage_funds"] is True
        assert perms["can_record_cotisation"] is True
        assert perms["can_grant_loan"] is False
        # Il ne gérait déjà pas le roster ni la clôture : inchangé.
        assert "can_manage_roster" not in perms  # hors catalogue depuis 2026-09
        assert perms["can_close"] is False
