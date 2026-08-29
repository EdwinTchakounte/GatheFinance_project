"""Tontines de GROUPE (réunions) — cagnotte partagée, rôles, versement
bénéficiaire, prêt/remboursement, visibilité restreinte."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.special_collections import group_services as gs
from apps_coop.special_collections.models import (
    GroupTontine,
    GroupTontineLoan,
    GroupTontineMember,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

_JAN = datetime.date(2026, 1, 1)
Role = GroupTontineMember.Role


def _group_with_roster():
    pres = MemberFactory()
    tres = MemberFactory()
    m3 = MemberFactory()
    group = gs.create_group(
        nom="Réunion quartier",
        montant_cotisation=Decimal("5000"),
        roster=[
            {"member": pres, "role": Role.PRESIDENT},
            {"member": tres, "role": Role.TRESORIER},
            {"member": m3, "role": Role.MEMBRE},
        ],
    )
    return group, pres, tres, m3


def _fund_pot(group, member, montant):
    """Alimente la cagnotte via cotisation depuis l'épargne classique."""
    ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(montant), date_ouverture=_JAN
    )
    gs.transfer_cotisation(group=group, member=member, montant=montant)


class TestRosterRoles:
    def test_create_group_and_roles(self):
        group, pres, tres, m3 = _group_with_roster()
        assert gs.role_of(group, pres) == Role.PRESIDENT
        assert gs.role_of(group, tres) == Role.TRESORIER
        assert gs.role_of(group, m3) == Role.MEMBRE
        assert group.members.filter(actif=True).count() == 3

    def test_president_can_change_treasurer(self):
        group, pres, tres, m3 = _group_with_roster()
        # m3 devient trésorier (revote).
        gs.set_role(group, m3, Role.TRESORIER, by=pres)
        assert gs.role_of(group, m3) == Role.TRESORIER

    def test_cannot_leave_group_without_president(self):
        group, pres, tres, m3 = _group_with_roster()
        # Rétrograder le seul président est refusé…
        with pytest.raises(gs.GroupTontineError, match="nouveau président"):
            gs.set_role(group, pres, Role.MEMBRE, by=pres)
        # …mais promouvoir un nouveau président d'abord, puis rétrograder, marche.
        gs.set_role(group, m3, Role.PRESIDENT, by=pres)
        gs.set_role(group, pres, Role.MEMBRE, by=pres)
        assert gs.role_of(group, pres) == Role.MEMBRE
        assert gs.role_of(group, m3) == Role.PRESIDENT


class TestCotisation:
    def test_transfer_cotisation_credits_pot(self):
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, m3, Decimal("8000"))
        group.refresh_from_db()
        assert group.solde == Decimal("8000")
        assert ClassicSavingsAccount.objects.get(member=m3).solde == Decimal("0")

    def test_transfer_cotisation_closed_group_does_not_debit(self):
        """Atomicité : sur une réunion clôturée, l'épargne N'EST PAS débitée
        (le débit et le crédit sont dans la même transaction)."""
        group, pres, tres, m3 = _group_with_roster()
        ClassicSavingsAccount.objects.create(
            member=m3, solde=Decimal("8000"), date_ouverture=_JAN
        )
        gs.close_group(group, by=pres)
        with pytest.raises(gs.GroupTontineError, match="clôturée"):
            gs.transfer_cotisation(group=group, member=m3, montant=Decimal("5000"))
        # L'épargne du membre est intacte (pas de débit orphelin).
        assert ClassicSavingsAccount.objects.get(member=m3).solde == Decimal("8000")


class TestPayout:
    def test_treasurer_pays_beneficiary(self):
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("20000"))
        # Le trésorier verse 12000 à m3 (montant fixé, pas le total).
        gs.payout_beneficiary(
            group=group, beneficiary=m3, montant=Decimal("12000"), by=tres
        )
        group.refresh_from_db()
        assert group.solde == Decimal("8000")  # 20000 - 12000
        assert ClassicSavingsAccount.objects.get(member=m3).solde == Decimal("12000")

    def test_plain_member_cannot_pay(self):
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("20000"))
        with pytest.raises(gs.GroupTontineError, match="autorisation"):
            gs.payout_beneficiary(
                group=group, beneficiary=pres, montant=Decimal("1000"), by=m3
            )

    def test_beneficiary_must_be_member(self):
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("20000"))
        outsider = MemberFactory()
        with pytest.raises(gs.GroupTontineError, match="membre de la réunion"):
            gs.payout_beneficiary(
                group=group, beneficiary=outsider, montant=Decimal("1000"), by=tres
            )

    def test_payout_capped_at_pot(self):
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("5000"))
        with pytest.raises(gs.GroupTontineError, match="Cagnotte insuffisante"):
            gs.payout_beneficiary(
                group=group, beneficiary=m3, montant=Decimal("9000"), by=tres
            )


class TestLoans:
    def test_grant_and_repay_loan_is_backed(self):
        """Le remboursement est ADOSSÉ : il débite l'épargne de l'emprunteur
        (ici l'argent prêté, crédité sur son épargne) — pas de crédit « ex nihilo »."""
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("30000"))
        loan, _row = gs.grant_loan(
            group=group, member=m3, montant=Decimal("10000"), by=pres
        )
        group.refresh_from_db()
        assert group.solde == Decimal("20000")
        assert ClassicSavingsAccount.objects.get(member=m3).solde == Decimal("10000")
        assert loan.solde_restant == Decimal("10000")

        # Remboursement partiel : débite l'épargne de m3, crédite la cagnotte.
        gs.repay_loan(loan=loan, montant=Decimal("4000"))
        loan.refresh_from_db()
        group.refresh_from_db()
        assert loan.solde_restant == Decimal("6000")
        assert group.solde == Decimal("24000")
        assert ClassicSavingsAccount.objects.get(member=m3).solde == Decimal("6000")

        gs.repay_loan(loan=loan, montant=Decimal("6000"))
        loan.refresh_from_db()
        group.refresh_from_db()
        assert loan.statut == GroupTontineLoan.Statut.SOLDE
        assert loan.solde_restant == Decimal("0")
        assert group.solde == Decimal("30000")  # cagnotte reconstituée
        assert ClassicSavingsAccount.objects.get(member=m3).solde == Decimal("0")

    def test_repay_fails_without_backing(self):
        """Sans épargne suffisante (et sans paiement), le remboursement est
        refusé — on ne crée jamais d'argent dans la cagnotte."""
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("30000"))
        loan, _ = gs.grant_loan(
            group=group, member=m3, montant=Decimal("10000"), by=pres
        )
        # m3 vide son épargne (retire les 10000 prêtés).
        acct = ClassicSavingsAccount.objects.get(member=m3)
        acct.solde = Decimal("0")
        acct.save(update_fields=["solde"])
        group.refresh_from_db()
        pot_avant = group.solde
        with pytest.raises(gs.GroupTontineError, match="insuffisante"):
            gs.repay_loan(loan=loan, montant=Decimal("5000"))
        group.refresh_from_db()
        assert group.solde == pot_avant  # cagnotte inchangée

    def test_repay_via_momo_payment(self):
        """Remboursement par versement direct (MoMo) : le hook route le paiement
        vers repay_loan — réduit le prêt + crédite la cagnotte, SANS toucher
        l'épargne (l'argent est réel)."""
        from decimal import Decimal as D

        from django.utils import timezone

        from apps_coop.payments.models import Payment
        from apps_coop.special_collections.group_services import credit_cotisation

        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, D("30000"))
        loan, _ = gs.grant_loan(group=group, member=m3, montant=D("10000"), by=pres)
        group.refresh_from_db()
        pot_avant = group.solde  # 20000
        pay = Payment.objects.create(
            member=m3, montant=D("6000"), type=Payment.Type.TONTINE_GROUPE,
            source=Payment.Source.MOBILE_MONEY, statut=Payment.Statut.VALIDE,
            date_versement=timezone.now(), date_validation=timezone.now(),
            group_tontine=group, group_loan=loan,
        )
        credit_cotisation(pay)
        loan.refresh_from_db()
        group.refresh_from_db()
        assert loan.solde_restant == D("4000")  # 10000 - 6000
        assert group.solde == pot_avant + D("6000")  # cagnotte recréditée
        # L'épargne de m3 n'est PAS touchée (paiement réel, pas un transfert).
        assert ClassicSavingsAccount.objects.get(member=m3).solde == D("10000")

    def test_repay_authorization(self):
        """Un tiers (ni emprunteur ni prés/trés) ne peut pas rembourser."""
        group, pres, tres, m3 = _group_with_roster()
        outsider = MemberFactory()
        gs.add_member(group, outsider, role=Role.MEMBRE)
        _fund_pot(group, pres, Decimal("30000"))
        loan, _ = gs.grant_loan(
            group=group, member=m3, montant=Decimal("10000"), by=pres
        )
        with pytest.raises(gs.GroupTontineError, match="emprunteur"):
            gs.repay_loan(loan=loan, montant=Decimal("1000"), by=outsider)


class TestVisibilityApi:
    def test_non_member_cannot_see_group(self):
        group, pres, tres, m3 = _group_with_roster()
        outsider = MemberFactory()
        c = APIClient()
        c.force_authenticate(user=outsider.user)
        r = c.get(f"/api/v1/special-collections/groups/{group.id}/")
        assert r.status_code == 403

    def test_member_sees_group_with_role(self):
        group, pres, tres, m3 = _group_with_roster()
        c = APIClient()
        c.force_authenticate(user=tres.user)
        r = c.get(f"/api/v1/special-collections/groups/{group.id}/")
        assert r.status_code == 200
        assert r.json()["my_role"] == Role.TRESORIER

    def test_action_response_returns_fresh_cagnotte(self):
        """Régression : la réponse d'une action (cotiser/payout) doit refléter
        la cagnotte APRÈS mutation, pas l'état périmé de l'objet de la vue."""
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("10000"))
        c = APIClient()
        c.force_authenticate(user=tres.user)
        # Payout 4000 → la réponse doit montrer 6000, pas 10000.
        r = c.post(
            f"/api/v1/special-collections/groups/{group.id}/payout/",
            {"beneficiary_id": m3.id, "montant": 4000}, format="json",
        )
        assert r.status_code == 200, r.content
        assert Decimal(r.json()["solde"]) == Decimal("6000")

    def test_my_groups_lists_only_mine(self):
        group, pres, tres, m3 = _group_with_roster()
        outsider = MemberFactory()
        c = APIClient()
        c.force_authenticate(user=outsider.user)
        assert c.get("/api/v1/special-collections/groups/").json() == []
        c2 = APIClient()
        c2.force_authenticate(user=pres.user)
        assert len(c2.get("/api/v1/special-collections/groups/").json()) == 1


class TestNotificationsAndActor:
    def test_transfer_cotisation_notifies_member(self):
        from apps_coop.notifications.models import Notification

        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, m3, Decimal("5000"))  # m3 cotise depuis son épargne
        notifs = Notification.objects.filter(user=m3.user, type="collecte.cotisation")
        assert notifs.exists()
        assert "épargne libre" in notifs.latest("id").message

    def test_payout_notifies_beneficiary_with_actor(self):
        from apps_coop.notifications.models import Notification

        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("20000"))
        gs.payout_beneficiary(
            group=group, beneficiary=m3, montant=Decimal("8000"), by=tres
        )
        notif = Notification.objects.filter(
            user=m3.user, type="collecte.beneficiaire"
        ).latest("id")
        # Mentionne l'acteur (le trésorier).
        assert f"{tres.prenom} {tres.nom}".strip() in notif.message

    def test_actor_name_in_group_transactions_api(self):
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("20000"))
        gs.payout_beneficiary(
            group=group, beneficiary=m3, montant=Decimal("5000"), by=tres
        )
        c = APIClient()
        c.force_authenticate(user=m3.user)
        r = c.get(f"/api/v1/special-collections/groups/{group.id}/")
        txns = r.json()["transactions"]
        payout = next(t for t in txns if t["type_op"] == "versement_beneficiaire")
        assert f"{tres.prenom} {tres.nom}".strip() in payout["acted_by_name"]


class TestRollback:
    def test_invalidate_reverses_group_cotisation(self):
        """Rollback : invalider un versement MoMo de cotisation débite la
        cagnotte (contre-passation)."""
        from decimal import Decimal as D

        from django.utils import timezone

        from apps_coop.payments.invalidation_services import invalidate_payment
        from apps_coop.payments.models import Payment
        from apps_coop.special_collections.group_services import credit_cotisation

        group, pres, tres, m3 = _group_with_roster()
        staff = _staff_member()
        pay = Payment.objects.create(
            member=m3, montant=D("50000"), type=Payment.Type.TONTINE_GROUPE,
            source=Payment.Source.MOBILE_MONEY, statut=Payment.Statut.VALIDE,
            date_versement=timezone.now(), date_validation=timezone.now(),
            group_tontine=group,
        )
        credit_cotisation(pay)
        group.refresh_from_db()
        assert group.solde == D("50000")
        # Erreur (500000 au lieu de 50000) → rollback.
        invalidate_payment(pay, actor=staff.user)
        group.refresh_from_db()
        assert group.solde == D("0")  # cagnotte ramenée
        pay.refresh_from_db()
        assert pay.statut == Payment.Statut.REJETE


def _staff_member():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m


class TestClose:
    def test_close_blocks_operations(self):
        group, pres, tres, m3 = _group_with_roster()
        _fund_pot(group, pres, Decimal("10000"))
        gs.close_group(group, by=pres)
        group.refresh_from_db()
        assert not group.is_open
        with pytest.raises(gs.GroupTontineError, match="clôturée"):
            gs.payout_beneficiary(
                group=group, beneficiary=m3, montant=Decimal("1000"), by=tres
            )
