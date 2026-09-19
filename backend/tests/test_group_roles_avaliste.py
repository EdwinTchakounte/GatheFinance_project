"""Tontines de groupe — rôles PERSONNALISÉS (actions rattachées) + avaliste
INFORMATIF sur les prêts.

Décisions 2026-08 :
  * un rôle custom (nom libre) cumule ses actions cochées par-dessus le rôle
    intégré ; le président garde toujours tout ;
  * l'avaliste d'un prêt de réunion est purement informatif (membre du roster OU
    nom libre), sans aucun impact financier ni lien avec l'avaliste crédit coop.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.special_collections import group_services as gs
from apps_coop.special_collections.models import (
    GroupTontineLoan,
    GroupTontineMember,
    GroupTontineRole,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

_JAN = datetime.date(2026, 1, 1)
Role = GroupTontineMember.Role


def _group():
    pres = MemberFactory()
    tres = MemberFactory()
    m3 = MemberFactory()
    group = gs.create_group(
        nom="Réunion quartier",
        roster=[
            {"member": pres, "role": Role.PRESIDENT},
            {"member": tres, "role": Role.TRESORIER},
            {"member": m3, "role": Role.MEMBRE},
        ],
    )
    return group, pres, tres, m3


def _fund_pot(group, member, montant):
    ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(montant), date_ouverture=_JAN
    )
    gs.transfer_cotisation(group=group, member=member, montant=montant)


# ---------------------------------------------------------------------------
# Permissions par rôle
# ---------------------------------------------------------------------------
class TestBuiltinPermissions:
    def test_president_has_all_actions(self):
        group, pres, _, _ = _group()
        perms = gs.member_permissions(group, pres)
        assert all(perms[f] for f in GroupTontineRole.ACTION_FIELDS)

    def test_tresorier_designe_le_beneficiaire_mais_ne_prete_plus(self):
        """Décision 2026-09 : le trésorier DÉSIGNE qui reçoit, il n'ENGAGE PAS
        la cagnotte sur une dette. Accorder un prêt revient au président ou au
        guichet, la coopérative détenant les fonds. Une réunion peut le lui
        rendre par un rôle personnalisé — l'exception devient explicite."""
        group, _, tres, _ = _group()
        perms = gs.member_permissions(group, tres)
        assert perms["can_manage_funds"] and perms["can_record_cotisation"]
        assert not perms["can_grant_loan"]
        assert not perms["can_close"]
        # `can_manage_roster` a quitté le catalogue (2026-09) : la gestion
        # des rôles revient à l'administrateur de la coopérative.
        assert "can_manage_roster" not in perms

    def test_plain_member_has_no_action(self):
        group, _, _, m3 = _group()
        perms = gs.member_permissions(group, m3)
        assert not any(perms[f] for f in GroupTontineRole.ACTION_FIELDS)

    def test_non_member_has_no_action(self):
        group, *_ = _group()
        outsider = MemberFactory()
        assert not any(gs.member_permissions(group, outsider).values())


# ---------------------------------------------------------------------------
# Rôle personnalisé — cumul d'actions
# ---------------------------------------------------------------------------
class TestCustomRole:
    def test_custom_role_grants_action_to_plain_member(self):
        group, _, _, m3 = _group()
        _fund_pot(group, m3, Decimal("20000"))
        # m3 (membre) ne peut pas verser…
        assert not gs.member_permissions(group, m3)["can_manage_funds"]
        # …on crée un rôle « Trésorier adjoint » habilité, on l'attribue à m3.
        role = gs.create_custom_role(
            group, "Trésorier adjoint", {"can_manage_funds": True}
        )
        gs.assign_custom_role(group, m3, role)
        assert gs.member_permissions(group, m3)["can_manage_funds"]
        # …et il peut désormais réellement verser.
        gs.payout_beneficiary(
            group=group, beneficiary=m3, montant=Decimal("1000"), by=m3
        )

    def test_custom_role_cumulates_over_builtin(self):
        group, _, tres, _ = _group()
        role = gs.create_custom_role(group, "Adjoint prêteur", {"can_grant_loan": True})
        gs.assign_custom_role(group, tres, role)
        perms = gs.member_permissions(group, tres)
        # Actions du trésorier CONSERVÉES + celle du rôle custom AJOUTÉE.
        # (`can_grant_loan` lui a été retiré en 2026-09 ; un rôle custom peut
        # le lui rendre — c'est justement le cumul qu'on vérifie ici.)
        assert perms["can_manage_funds"] and perms["can_grant_loan"]

    def test_unassign_role_removes_action(self):
        group, _, _, m3 = _group()
        role = gs.create_custom_role(group, "Adjoint", {"can_grant_loan": True})
        gs.assign_custom_role(group, m3, role)
        assert gs.member_permissions(group, m3)["can_grant_loan"]
        gs.assign_custom_role(group, m3, None)
        assert not gs.member_permissions(group, m3)["can_grant_loan"]

    def test_duplicate_role_name_rejected(self):
        group, *_ = _group()
        gs.create_custom_role(group, "Commissaire", {})
        with pytest.raises(gs.GroupTontineError, match="déjà ce nom"):
            gs.create_custom_role(group, "commissaire", {})

    def test_delete_role_nulls_member_link(self):
        group, _, _, m3 = _group()
        role = gs.create_custom_role(group, "Éphémère", {"can_close": True})
        gs.assign_custom_role(group, m3, role)
        gs.delete_custom_role(role)
        m3.refresh_from_db()
        row = GroupTontineMember.objects.get(group=group, member=m3)
        assert row.custom_role_id is None
        assert not gs.member_permissions(group, m3)["can_close"]


# ---------------------------------------------------------------------------
# Avaliste informatif sur les prêts
# ---------------------------------------------------------------------------
class TestLoanAvaliste:
    def test_loan_with_member_avaliste(self):
        group, pres, _, m3 = _group()
        _fund_pot(group, pres, Decimal("20000"))
        loan, _ = gs.grant_loan(
            group=group, member=m3, montant=Decimal("5000"), by=pres, avaliste=pres
        )
        loan.refresh_from_db()
        assert loan.avaliste_id == pres.id
        assert loan.avaliste_nom == ""

    def test_loan_with_free_text_avaliste(self):
        group, pres, _, m3 = _group()
        _fund_pot(group, pres, Decimal("20000"))
        loan, _ = gs.grant_loan(
            group=group, member=m3, montant=Decimal("5000"), by=pres,
            avaliste_nom="Tonton Paul (voisin)",
        )
        loan.refresh_from_db()
        assert loan.avaliste_id is None
        assert loan.avaliste_nom == "Tonton Paul (voisin)"

    def test_avaliste_has_no_financial_impact(self):
        """L'avaliste ne gèle rien et n'est pas débité — son épargne est intacte
        (contraste avec l'avaliste crédit coopérative)."""
        group, pres, tres, m3 = _group()
        _fund_pot(group, pres, Decimal("20000"))
        # tres = avaliste, avec une épargne propre qui NE DOIT PAS bouger.
        ClassicSavingsAccount.objects.create(
            member=tres, solde=Decimal("8000"), date_ouverture=_JAN
        )
        group.refresh_from_db()
        pot_before = group.solde
        gs.grant_loan(
            group=group, member=m3, montant=Decimal("5000"), by=pres, avaliste=tres
        )
        group.refresh_from_db()
        # La cagnotte ne baisse que du prêt ; l'avaliste (tres) n'est pas prélevé.
        assert group.solde == pot_before - Decimal("5000")
        assert ClassicSavingsAccount.objects.get(member=tres).solde == Decimal("8000")


# ---------------------------------------------------------------------------
# Endpoints (API) — rôles personnalisés + avaliste
# ---------------------------------------------------------------------------
def _client(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


_BASE = "/api/v1/special-collections/groups"


class TestRoleApi:
    """2026-09 — la gestion des rôles a QUITTÉ le canal membre.

    Décider qui préside une réunion, qui tient ses fonds ou qui y entre engage
    la coopérative, pas seulement le groupe : ça ne se règle plus depuis un
    téléphone. Ces tests figent la fermeture du canal, pour qu'une remise en
    service accidentelle se voie.
    """

    @pytest.mark.parametrize(
        "chemin,methode,corps",
        [
            ("roles/", "post", {"nom": "Pirate", "permissions": {"can_manage_funds": True}}),
            ("assign-role/", "post", {"member_id": 1, "custom_role_id": None}),
            ("role/", "post", {"member_id": 1, "role": "president"}),
        ],
    )
    def test_le_canal_membre_est_ferme(self, chemin, methode, corps):
        group, pres, _, _ = _group()
        # Même le PRÉSIDENT, qui pouvait tout faire avant, n'y a plus accès.
        r = getattr(_client(pres), methode)(
            f"{_BASE}/{group.id}/{chemin}", corps, format="json",
        )
        assert r.status_code in (404, 405), (chemin, r.status_code)

    def test_ladmin_prend_le_relais(self):
        """Le besoin reste couvert — ailleurs."""
        group, _, _, m3 = _group()
        staff = MemberFactory()
        staff.user.is_staff = True
        staff.user.is_superuser = True
        staff.user.save(update_fields=["is_staff", "is_superuser"])

        r = _client(staff).post(
            f"/api/v1/special-collections/admin/groups/{group.id}/role/",
            {"member_id": m3.id, "role": "tresorier"},
            format="json",
        )

        assert r.status_code == 200, r.content
        ligne = next(m for m in r.json()["members"] if m["member_id"] == m3.id)
        assert ligne["role"] == "tresorier"

    def test_les_roles_restent_lisibles_par_les_membres(self):
        """On ferme l'écriture, pas la lecture : le membre voit toujours qui
        fait quoi dans sa réunion."""
        group, pres, _, _ = _group()
        gs.create_custom_role(group, "Adjoint", {"can_grant_loan": True})

        r = _client(pres).get(f"{_BASE}/{group.id}/")

        assert r.status_code == 200
        assert [x["nom"] for x in r.json()["custom_roles"]] == ["Adjoint"]

    def test_my_permissions_exposed_in_detail(self):
        group, pres, _, _ = _group()
        r = _client(pres).get(f"{_BASE}/{group.id}/")
        assert r.status_code == 200
        assert r.json()["my_permissions"]["can_close"] is True

    def test_custom_role_unlocks_action_end_to_end(self):
        """L'ADMIN attribue le rôle, le MEMBRE agit.

        C'est la nouvelle répartition : la coopérative décide qui peut quoi,
        le groupe exécute. Le rôle custom reste donc pleinement opérant — seul
        son point d'attribution a changé.
        """
        group, pres, _, m3 = _group()
        _fund_pot(group, pres, Decimal("10000"))
        staff = MemberFactory()
        staff.user.is_staff = True
        staff.user.is_superuser = True
        staff.user.save(update_fields=["is_staff", "is_superuser"])
        cadmin = _client(staff)
        admin_base = f"/api/v1/special-collections/admin/groups/{group.id}"

        role_id = cadmin.post(
            f"{admin_base}/roles/",
            {"nom": "Payeur", "permissions": {"can_manage_funds": True}},
            format="json",
        ).json()["custom_roles"][0]["id"]
        cadmin.post(
            f"{admin_base}/assign-role/",
            {"member_id": m3.id, "custom_role_id": role_id}, format="json",
        )

        # m3 (membre + rôle Payeur) verse sans être président ni trésorier.
        r = _client(m3).post(
            f"{_BASE}/{group.id}/payout/",
            {"beneficiary_id": m3.id, "montant": 2000}, format="json",
        )
        assert r.status_code == 200, r.content
        assert Decimal(r.json()["solde"]) == Decimal("8000")


class TestLoanAvalisteApi:
    def test_grant_loan_with_avaliste_member_via_api(self):
        group, pres, tres, m3 = _group()
        _fund_pot(group, pres, Decimal("20000"))
        r = _client(pres).post(
            f"{_BASE}/{group.id}/loan/",
            {"member_id": m3.id, "montant": 5000, "avaliste_id": tres.id},
            format="json",
        )
        assert r.status_code == 200, r.content
        loan = r.json()["loans"][0]
        assert loan["avaliste_id"] == tres.id
        assert loan["avaliste_display"]

    def test_grant_loan_with_free_text_avaliste_via_api(self):
        group, pres, _, m3 = _group()
        _fund_pot(group, pres, Decimal("20000"))
        r = _client(pres).post(
            f"{_BASE}/{group.id}/loan/",
            {"member_id": m3.id, "montant": 5000, "avaliste_nom": "Voisin Paul"},
            format="json",
        )
        assert r.status_code == 200, r.content
        loan = r.json()["loans"][0]
        assert loan["avaliste_id"] is None
        assert loan["avaliste_display"] == "Voisin Paul"
