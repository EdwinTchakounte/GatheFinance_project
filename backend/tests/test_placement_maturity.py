"""Placement — restitution à échéance (date fixe éditable) + intérêts prorata.

À la date de restitution, chaque placement DISPONIBLE est restitué : intérêts
prorata crédités sur l'épargne classique + tranche passée à LIBEREE (capital de
nouveau retirable). Les tranches ENGAGEE/GELEE ne sont pas touchées.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AppSetting
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderTranche,
)
from apps_coop.savings.placement_maturity import (
    is_maturity_day,
    placement_maturity_mmdd,
    process_placement_maturity,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _rate(v: str = "0.01"):
    AppSetting.objects.update_or_create(
        cle="epargne.placement.interest_rate", defaults={"valeur": v}
    )


def _tranche(member, montant, *, statut=LenderTranche.Statut.DISPONIBLE, age_days=60):
    tr = LenderTranche.objects.create(
        member=member, montant=Decimal(montant), statut=statut
    )
    # created_at est auto_now_add → on le repousse dans le passé via .update().
    LenderTranche.objects.filter(pk=tr.pk).update(
        created_at=timezone.now() - timedelta(days=age_days)
    )
    return LenderTranche.objects.get(pk=tr.pk)


def _classic(member, solde="50000"):
    return ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(solde), date_ouverture=date.today()
    )


class TestProcess:
    def test_restitue_avec_interets_prorata_et_libere(self):
        _rate("0.01")
        m = MemberFactory()
        acc = _classic(m, "50000")
        _tranche(m, "50000", age_days=60)  # 2 mois

        summary = process_placement_maturity(date.today())

        assert summary["processed"] == 1
        acc.refresh_from_db()
        # intérêt = 50 000 × 0.01 × (60/30) = 1 000
        assert acc.solde == Decimal("51000.00")
        tr = LenderTranche.objects.get(member=m)
        assert tr.statut == LenderTranche.Statut.LIBEREE
        assert tr.released_at is not None
        # une écriture INTERET_PLACEMENT
        assert ClassicSavingsTransaction.objects.filter(
            account=acc,
            type_op=ClassicSavingsTransaction.TypeOp.INTERET_PLACEMENT,
            montant=Decimal("1000.00"),
        ).exists()

    def test_ne_touche_pas_les_tranches_engagees(self):
        _rate("0.01")
        m = MemberFactory()
        _classic(m, "50000")
        _tranche(m, "50000", statut=LenderTranche.Statut.ENGAGEE, age_days=60)

        summary = process_placement_maturity(date.today())
        assert summary["processed"] == 0
        tr = LenderTranche.objects.get(member=m)
        assert tr.statut == LenderTranche.Statut.ENGAGEE

    def test_taux_editable(self):
        _rate("0.02")  # 2%/mois
        m = MemberFactory()
        acc = _classic(m, "10000")
        _tranche(m, "10000", age_days=30)  # 1 mois

        process_placement_maturity(date.today())
        acc.refresh_from_db()
        # 10 000 × 0.02 × (30/30) = 200
        assert acc.solde == Decimal("10200.00")


class TestMaturityDate:
    def test_defaut_1er_janvier(self):
        AppSetting.objects.filter(cle="epargne.placement.maturity_date").delete()
        assert placement_maturity_mmdd() == "01-01"
        assert is_maturity_day(date(2027, 1, 1)) is True
        assert is_maturity_day(date(2027, 6, 15)) is False

    def test_date_editable(self):
        AppSetting.objects.update_or_create(
            cle="epargne.placement.maturity_date", defaults={"valeur": "06-30"}
        )
        assert placement_maturity_mmdd() == "06-30"
        assert is_maturity_day(date(2027, 6, 30)) is True
        assert is_maturity_day(date(2027, 1, 1)) is False


class TestCron:
    def test_cron_agit_seulement_au_jour_decheance(self):
        from apps_coop.savings.tasks import placement_maturity_processing

        # Date de maturité = demain → aujourd'hui n'est pas le jour → skip.
        tomorrow = date.today() + timedelta(days=1)
        AppSetting.objects.update_or_create(
            cle="epargne.placement.maturity_date",
            defaults={"valeur": f"{tomorrow.month:02d}-{tomorrow.day:02d}"},
        )
        out = placement_maturity_processing()
        assert out.get("skipped") is True

    def test_cron_desactivable(self):
        from apps_coop.savings.tasks import placement_maturity_processing

        AppSetting.objects.update_or_create(
            cle="epargne.placement.maturity.enabled", defaults={"valeur": "false"}
        )
        out = placement_maturity_processing()
        assert out.get("skipped") is True
