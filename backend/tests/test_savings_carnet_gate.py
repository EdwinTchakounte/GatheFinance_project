"""Garde « une écriture ne se fait que dans un carnet » — collecte + épargne.

Décision 2026-08 (cohérence rapports/audit) : aucun versement (collecte
journalière OU épargne classique) n'est accepté tant que le membre ne possède
pas de carnet ``collecte``. Le blocage existait déjà pour tontine/caisse (chacun
son carnet) ; on l'étend ici aux deux produits qui partagent le carnet collecte.

Les deux canaux de versement sont couverts :
  * membre self-service — ``POST /payments/init/`` ;
  * versement manuel agence — ``POST /payments/admin/cash-in/``.

Un membre activé porte normalement un carnet (vendu aux frais d'activation) ;
la ``MemberFactory`` le reflète. Pour tester le refus, on retire le carnet via
``MemberFactory(with_carnet=False)``.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps_coop.members.models import BookletOrder
from apps_coop.payments.models import Payment
from apps_coop.savings.models import (
    ClassicSavingsTransaction,
    SavingsTransaction,
)
from tests.factories import MemberFactory, grant_carnet


pytestmark = pytest.mark.django_db

INIT = "/api/v1/payments/init/"
CASH_IN = "/api/v1/payments/admin/cash-in/"


def _member_client(member) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def _admin_client(admin_user) -> APIClient:
    c = APIClient()
    c.force_authenticate(admin_user)
    return c


# ---------------------------------------------------------------------------
# Canal membre — POST /payments/init/
# ---------------------------------------------------------------------------
class TestInitCarnetGate:
    def test_collecte_without_carnet_refused(self):
        member = MemberFactory(with_carnet=False)
        r = _member_client(member).post(
            INIT,
            {"type": "epargne", "montant": "1000", "phone": "699000000", "network": "MTN"},
            format="json",
        )
        assert r.status_code == 400, r.content
        assert b"carnet" in r.content
        assert not SavingsTransaction.objects.filter(account__member=member).exists()

    def test_classique_without_carnet_refused(self):
        member = MemberFactory(with_carnet=False)
        r = _member_client(member).post(
            INIT,
            {"type": "epargne_classique", "montant": "5000", "phone": "699000000", "network": "MTN"},
            format="json",
        )
        assert r.status_code == 400, r.content
        assert b"carnet" in r.content
        assert not ClassicSavingsTransaction.objects.filter(
            account__member=member
        ).exists()

    def test_collecte_with_carnet_accepted(self):
        member = MemberFactory()  # porte un carnet collecte
        assert BookletOrder.latest_for(member, BookletOrder.Type.COLLECTE) is not None
        r = _member_client(member).post(
            INIT,
            {"type": "epargne", "montant": "1000", "phone": "699000000", "network": "MTN"},
            format="json",
        )
        assert r.status_code in (200, 201), r.content


# ---------------------------------------------------------------------------
# Canal agence — POST /payments/admin/cash-in/
# ---------------------------------------------------------------------------
class TestCashInCarnetGate:
    def test_collecte_cashin_without_carnet_refused(self, admin_user):
        member = MemberFactory(with_carnet=False)
        r = _admin_client(admin_user).post(
            CASH_IN,
            {"member_id": member.id, "type": "epargne", "montant": "1000"},
            format="json",
        )
        assert r.status_code == 400, r.content
        assert b"carnet" in r.content
        assert not SavingsTransaction.objects.filter(account__member=member).exists()

    def test_classique_cashin_without_carnet_refused(self, admin_user):
        member = MemberFactory(with_carnet=False)
        r = _admin_client(admin_user).post(
            CASH_IN,
            {"member_id": member.id, "type": "epargne_classique", "montant": "5000"},
            format="json",
        )
        assert r.status_code == 400, r.content
        assert b"carnet" in r.content
        assert not ClassicSavingsTransaction.objects.filter(
            account__member=member
        ).exists()

    def test_cashin_accepted_once_carnet_sold(self, admin_user):
        """Refus tant que pas de carnet, puis ACCEPTÉ après vente du carnet —
        le parcours de rattrapage agence (« vends-lui un carnet »)."""
        member = MemberFactory(with_carnet=False)
        c = _admin_client(admin_user)

        r = c.post(
            CASH_IN,
            {"member_id": member.id, "type": "epargne", "montant": "1000"},
            format="json",
        )
        assert r.status_code == 400, r.content

        grant_carnet(member, BookletOrder.Type.COLLECTE)

        r = c.post(
            CASH_IN,
            {"member_id": member.id, "type": "epargne", "montant": "1000"},
            format="json",
        )
        assert r.status_code == 201, r.content
        assert SavingsTransaction.objects.filter(
            account__member=member,
            type_op=SavingsTransaction.TypeOp.DEPOT,
        ).count() == 1
