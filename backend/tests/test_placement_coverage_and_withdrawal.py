"""Lot D — validation des règles confirmées (points ① et ④).

① Une épargne en PLACEMENT (qui « tourne ») compte dans la couverture d'un
   crédit : si le solde classique (placement inclus) couvre le montant, la voie
   auto-couverture matche → le comité peut accepter.

④ Un retrait d'épargne libre peut se faire vers Mobile Money (OM/MTN) OU en
   présentiel à l'agence — dans les deux cas c'est enregistré dans le système
   (une ``WithdrawalRequest`` est créée).

Ces comportements existent déjà ; ces tests les VERROUILLENT contre les
régressions.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps_coop.loans.eligibility_routing import EligibilityRoute, evaluate_routes
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    LenderTranche,
    WithdrawalRequest,
)
from apps_coop.savings.services import request_withdrawal

from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


def _classic(member, solde):
    acc, _ = ClassicSavingsAccount.objects.get_or_create(
        member=member,
        defaults={"solde": Decimal("0"), "date_ouverture": date.today()},
    )
    acc.solde = Decimal(solde)
    acc.save(update_fields=["solde"])
    return acc


# ---------------------------------------------------------------------------
# ① Placement en cours → compte dans la couverture crédit
# ---------------------------------------------------------------------------


class TestPlacementCountsTowardCoverage:
    def test_savings_fully_in_placement_still_cover_credit(self):
        m = MemberFactory()
        _classic(m, Decimal("100000"))
        # Tout le solde est en placement actif (une tranche prêteur DISPONIBLE).
        LenderTranche.objects.create(
            member=m,
            montant=Decimal("100000"),
            statut=LenderTranche.Statut.DISPONIBLE,
        )
        acc = m.classic_savings_account
        assert acc.solde_placement_actif == Decimal("100000")
        assert acc.solde_libre == Decimal("0")

        # Le placement compte dans la couverture → auto-couverture matche.
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.SENIOR_BRC
        assert result.details["auto_couverture"] is True

    def test_placement_running_does_not_block_a_new_credit(self):
        # Placement 100k, crédit demandé 60k ≤ solde → couvert malgré le placement.
        m = MemberFactory()
        _classic(m, Decimal("100000"))
        LenderTranche.objects.create(
            member=m,
            montant=Decimal("100000"),
            statut=LenderTranche.Statut.DISPONIBLE,
        )
        result = evaluate_routes(m, montant=Decimal("60000"))
        assert result.eligible is True
        assert result.route == EligibilityRoute.SENIOR_BRC


# ---------------------------------------------------------------------------
# ④ Retrait épargne libre → Mobile Money OU agence, tracé dans les 2 cas
# ---------------------------------------------------------------------------


class TestFreeSavingsWithdrawalChannels:
    def test_withdraw_to_mobile_money_is_recorded(self, active_member):
        acc = _classic(active_member, Decimal("50000"))
        wr = request_withdrawal(
            montant=Decimal("10000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            classic_account=acc,
            mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
            recipient_phone="+237690000000",
            network="MTN",
        )
        assert wr.pk is not None
        assert wr.mode_paiement == WithdrawalRequest.ModePaiement.MOMO
        assert wr.recipient_phone == "+237690000000"
        assert wr.network == "MTN"
        assert wr.source == WithdrawalRequest.Source.CLASSIQUE_LIBRE
        assert wr.statut == WithdrawalRequest.Statut.EN_ATTENTE

    def test_withdraw_at_agency_is_recorded(self, active_member):
        acc = _classic(active_member, Decimal("50000"))
        wr = request_withdrawal(
            montant=Decimal("10000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            classic_account=acc,
            mode_paiement=WithdrawalRequest.ModePaiement.PRESENTIEL,
        )
        assert wr.pk is not None
        assert wr.mode_paiement == WithdrawalRequest.ModePaiement.PRESENTIEL
        # En présentiel, pas de destination Mobile Money.
        assert wr.recipient_phone == ""
        assert wr.network == ""
        assert wr.statut == WithdrawalRequest.Statut.EN_ATTENTE
