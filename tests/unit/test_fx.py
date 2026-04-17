from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
from django.core.cache import cache

from apps.fx.models import FxRate
from apps.fx.services import cache_key, get_rate
from tasks.fx import fetch_fx_rates
from tests.factories import make_account

pytestmark = pytest.mark.django_db

DAY = date(2026, 4, 1)


def test_same_currency_is_one() -> None:
    assert get_rate("RUB", "RUB", DAY) == Decimal("1")


def test_provider_result_is_persisted_and_cached() -> None:
    assert get_rate("USD", "RUB", DAY) == Decimal("92.50")
    assert FxRate.objects.get(base="USD", quote="RUB", effective_on=DAY).rate == Decimal("92.50")
    assert cache.get(cache_key("USD", "RUB", DAY)) == "92.50"


def test_db_rate_wins_over_provider() -> None:
    FxRate.objects.create(base="USD", quote="RUB", effective_on=DAY, rate=Decimal("90"))
    assert get_rate("USD", "RUB", DAY) == Decimal("90")


def test_cache_outage_falls_back_to_provider() -> None:
    with mock.patch("apps.fx.services.cache.get", side_effect=ConnectionError("down")):
        assert get_rate("EUR", "RUB", DAY) == Decimal("100.00")


def test_unknown_pair_is_none() -> None:
    assert get_rate("JPY", "RUB", DAY) is None


def test_fetch_task_covers_currencies_in_use(user: Any, settings: Any) -> None:
    settings.FX_BASE_CURRENCY = "RUB"
    make_account(user, "USD", name="U")
    make_account(user, "RUB", name="R")
    assert fetch_fx_rates() == {"USD/RUB": "92.50"}
