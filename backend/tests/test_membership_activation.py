"""CH-2 — Activation du Member après paiement complet des 3 frais.

Couvre la règle métier introduite dans le chantier juin 2026 : un nouveau
membre approuvé reste ``SUSPENDU`` tant qu'il n'a pas réglé les 3 frais
(adhésion 10 000 + inscription 2 000 + carnet 1 000 = 13 000 FCFA). Le
basculement à ``ACTIF`` est déclenché par le paiement qui complète le
triplet, peu importe son ordre d'arrivée.

Le hook est dans ``apps_coop.payments.services._activate_member_if_fees_settled``.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.members.models import Member
from apps_coop.payments.models import Payment
from apps_coop.payments.services import (
    _membership_fees_settled,
    handle_webhook_event,
)


pytestmark = pytest.mark.django_db


def _make_payment(member, *, type_: str, montant: str) -> Payment:
    """Crée un Payment en attente (idempotency_key auto)."""
    return Payment.objects.create(
        member=member,
        montant=Decimal(montant),
        type=type_,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.EN_ATTENTE,
        provider_code="tara",
        date_versement=timezone.now(),
    )


def _validate(payment: Payment) -> None:
    """Simule la confirmation Tara du paiement (déclenche son hook)."""
    handle_webhook_event(
        payment.idempotency_key,
        "valide",
        provider_reference=f"TX-{payment.id}",
        raw_payload={},
    )


class TestMembershipFeesSettledHelper:
    """Le helper de lecture pure ``_membership_fees_settled``."""

    def test_no_payment_returns_false(self, suspended_member):
        assert _membership_fees_settled(suspended_member) is False

    def test_only_adhesion_paid_returns_false(self, suspended_member):
        p = _make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000")
        _validate(p)
        assert _membership_fees_settled(suspended_member) is False

    def test_adhesion_and_inscription_paid_returns_false(self, suspended_member):
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_INSCRIPTION, montant="2000"))
        assert _membership_fees_settled(suspended_member) is False

    def test_all_three_paid_returns_true(self, suspended_member):
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_INSCRIPTION, montant="2000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_CARNET, montant="1000"))
        assert _membership_fees_settled(suspended_member) is True

    def test_pending_payment_does_not_count(self, suspended_member):
        # 3 paiements créés mais non validés
        _make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000")
        _make_payment(suspended_member, type_=Payment.Type.FRAIS_INSCRIPTION, montant="2000")
        _make_payment(suspended_member, type_=Payment.Type.FRAIS_CARNET, montant="1000")
        assert _membership_fees_settled(suspended_member) is False


class TestActivationOnCompleteFees:
    """Le hook bascule le Member à ACTIF UNIQUEMENT au triplet complet."""

    def test_only_adhesion_keeps_member_suspended(self, suspended_member):
        assert suspended_member.statut == Member.Statut.SUSPENDU
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.SUSPENDU

    def test_two_fees_keep_member_suspended(self, suspended_member):
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_INSCRIPTION, montant="2000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.SUSPENDU

    def test_all_three_fees_activates_member(self, suspended_member):
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_INSCRIPTION, montant="2000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_CARNET, montant="1000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.ACTIF

    def test_activation_works_regardless_of_payment_order(self, suspended_member):
        """Carnet en 1er, puis inscription, puis adhésion → activation."""
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_CARNET, montant="1000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.SUSPENDU

        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_INSCRIPTION, montant="2000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.SUSPENDU

        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.ACTIF

    def test_carnet_completing_fees_activates_member(self, suspended_member):
        """Vérifie que le hook _hook_carnet_fees déclenche aussi l'activation
        (régression : avant CH-2, le carnet créait juste BookletOrder)."""
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_INSCRIPTION, montant="2000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.SUSPENDU

        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_CARNET, montant="1000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.ACTIF

    def test_extra_payment_after_activation_is_noop(self, suspended_member):
        """Replay / 4e paiement après activation → statut stable + 1 seul email."""
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_ADHESION, montant="10000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_INSCRIPTION, montant="2000"))
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_CARNET, montant="1000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.ACTIF

        # Hypothèse : un second carnet (replay ou erreur de saisie) ne re-bascule rien.
        _validate(_make_payment(suspended_member, type_=Payment.Type.FRAIS_CARNET, montant="1000"))
        suspended_member.refresh_from_db()
        assert suspended_member.statut == Member.Statut.ACTIF
