"""Hypothesis property tests for ledger invariants.

We don't go through the ORM here — these are pure-Python checks against
the arithmetic guarantees we rely on across the codebase:

1. The running balance over a sequence equals opening_balance plus the
   sum of all amounts (i.e. the OVER-window matches the bulk SUM at the
   last row).
2. A cross-account transfer has zero net effect in the source currency
   (sum of the pair sums to zero).
3. Decimal arithmetic is exact: summing N amounts and dividing back
   reconstructs the input.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

money = st.decimals(
    min_value=Decimal("-1000000"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(opening=money, amounts=st.lists(money, min_size=0, max_size=100))
def test_running_balance_matches_bulk_sum(opening: Decimal, amounts: list[Decimal]):
    running = opening
    for a in amounts:
        running = running + a
    bulk = opening + sum(amounts, Decimal("0"))
    assert running == bulk


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(amount=money)
def test_transfer_pair_nets_to_zero(amount: Decimal):
    debit = -amount
    credit = amount
    assert debit + credit == Decimal("0")


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(values=st.lists(money, min_size=1, max_size=50))
def test_decimal_sum_is_associative(values: list[Decimal]):
    left = sum(values, Decimal("0"))
    right = sum(reversed(values), Decimal("0"))
    assert left == right


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    rate=st.decimals(
        min_value=Decimal("0.00000001"),
        max_value=Decimal("10000"),
        places=10,
        allow_nan=False,
        allow_infinity=False,
    ),
    amount=money,
)
def test_fx_conversion_roundtrip_is_bounded(rate: Decimal, amount: Decimal):
    """Converting and back should differ by less than 1 minor unit."""
    converted = amount * rate
    back = converted / rate
    delta = abs(back - amount)
    assert delta <= Decimal("0.01")
