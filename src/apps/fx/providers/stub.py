"""Deterministic stub FX provider used for tests and local development.

Rates are fixed per base/quote pair (date-independent). The inverse pair is
computed on the fly so we don't have to enumerate both directions.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

_RATES: dict[tuple[str, str], Decimal] = {
    ("USD", "RUB"): Decimal("92.50"),
    ("EUR", "RUB"): Decimal("100.00"),
    ("USD", "EUR"): Decimal("0.9250"),
    ("RUB", "RUB"): Decimal("1.0"),
}


class StubProvider:
    def fetch(self, base: str, quote: str, on: date) -> Decimal | None:
        if base == quote:
            return Decimal("1")
        if (base, quote) in _RATES:
            return _RATES[(base, quote)]
        if (quote, base) in _RATES:
            return Decimal("1") / _RATES[(quote, base)]
        return None
