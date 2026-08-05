"""L2 — la date de maturité de l'épargne classique doit être amorcée à la
création du compte, sinon le cron d'anniversaire ignore le compte (cycle 12
mois jamais déclenché)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.savings.services import _add_months, ensure_classic_maturity
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


def test_sets_maturity_when_missing():
    m = MemberFactory()
    acc = ClassicSavingsAccount.objects.create(
        member=m, solde=Decimal("0"), date_ouverture=date(2026, 1, 15)
    )
    assert acc.date_prochaine_maturite is None
    ensure_classic_maturity(acc)
    acc.refresh_from_db()
    assert acc.date_prochaine_maturite == _add_months(date(2026, 1, 15), 12)


def test_idempotent_keeps_existing_maturity():
    m = MemberFactory()
    fixed = date(2027, 3, 1)
    acc = ClassicSavingsAccount.objects.create(
        member=m,
        solde=Decimal("0"),
        date_ouverture=date(2026, 3, 1),
        date_prochaine_maturite=fixed,
    )
    ensure_classic_maturity(acc)
    acc.refresh_from_db()
    assert acc.date_prochaine_maturite == fixed  # inchangé
