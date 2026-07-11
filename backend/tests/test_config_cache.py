"""Cache des config-helpers (AppSetting / RateParam) + invalidation à l'écriture."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.cache import cache

from apps_coop.audit.models import AppSetting
from apps_coop.audit.services import get_str_setting
from apps_coop.payments.models import RateParam
from apps_coop.payments.rates import get_rate

pytestmark = pytest.mark.django_db


class TestConfigCache:
    def setup_method(self):
        cache.clear()

    def test_setting_cached_then_no_query(self, django_assert_num_queries):
        AppSetting.objects.create(cle="x.cache.test", valeur="A")
        assert get_str_setting("x.cache.test", "def") == "A"  # 1re lecture (DB)
        with django_assert_num_queries(0):  # 2e = servie par le cache
            assert get_str_setting("x.cache.test", "def") == "A"

    def test_setting_invalidated_on_save(self):
        s = AppSetting.objects.create(cle="y.cache.test", valeur="A")
        assert get_str_setting("y.cache.test", "def") == "A"
        s.valeur = "B"
        s.save()  # signal → purge
        assert get_str_setting("y.cache.test", "def") == "B"

    def test_rate_cached_then_no_query(self, django_assert_num_queries):
        RateParam.objects.create(
            code=RateParam.Code.LOAN_INTEREST, libelle="x", valeur=Decimal("0.10")
        )
        assert get_rate(RateParam.Code.LOAN_INTEREST) == Decimal("0.10")
        with django_assert_num_queries(0):
            assert get_rate(RateParam.Code.LOAN_INTEREST) == Decimal("0.10")

    def test_rate_invalidated_on_save(self):
        r = RateParam.objects.create(
            code=RateParam.Code.LATE_PENALTY, libelle="x", valeur=Decimal("0.50")
        )
        assert get_rate(RateParam.Code.LATE_PENALTY) == Decimal("0.50")
        r.valeur = Decimal("0.60")
        r.save()
        assert get_rate(RateParam.Code.LATE_PENALTY) == Decimal("0.60")
