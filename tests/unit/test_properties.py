"""Hypothesis property tests against the real code paths."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apps.analytics.queries.running_balance import running_balances_for
from apps.imports.parsers import ParsedRow, _to_decimal, disambiguate
from apps.ledger.models import Transaction
from tests.factories import make_account

money = st.decimals(
    min_value=Decimal("-1000000"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


@given(value=money)
def test_ru_formatted_amount_roundtrips(value: Decimal) -> None:
    whole, frac = f"{abs(value):,.2f}".split(".")
    ru = ("-" if value < 0 else "") + whole.replace(",", "\u00a0") + "," + frac
    assert _to_decimal(ru) == value


@given(hashes=st.lists(st.sampled_from(["a", "b", "c"]), max_size=30))
def test_disambiguated_hashes_are_unique(hashes: list[str]) -> None:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [ParsedRow(when, Decimal(0), "RUB", "", h) for h in hashes]
    out = [r.raw_hash for r in disambiguate(rows)]
    assert len(set(out)) == len(out)


@pytest.mark.django_db
@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(amounts=st.lists(money, min_size=1, max_size=20))
def test_running_balance_ends_at_bulk_sum(user: Any, amounts: list[Decimal]) -> None:
    account = make_account(user)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    txs = [
        Transaction.objects.create(
            user=user,
            account=account,
            amount=a,
            currency="RUB",
            occurred_at=start + timedelta(hours=i),
        )
        for i, a in enumerate(amounts)
    ]
    balances = running_balances_for([t.pk for t in txs], user.pk)
    assert balances[txs[-1].pk] == sum(amounts, Decimal("0"))
    Transaction.objects.filter(account=account).delete()
    account.delete()
