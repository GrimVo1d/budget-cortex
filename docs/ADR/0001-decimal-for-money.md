# ADR-0001: Decimal for money, never float

**Status:** Accepted
**Date:** 2026-04-10

## Context

Every amount in the ledger is money. Floating-point arithmetic is unsuitable: `0.1 + 0.2 = 0.30000000000000004`, rounding modes are platform-dependent, and cumulative errors grow with the number of operations.

## Decision

All monetary fields use `Decimal` end-to-end:

- DB: `NUMERIC(14, 2)` for amounts, `NUMERIC(20, 10)` for FX rates.
- Models: `models.DecimalField(max_digits=14, decimal_places=2)`.
- Python: `decimal.Decimal` everywhere, never `float`.
- DRF: serializers default to string output for decimals (`COERCE_DECIMAL_TO_STRING=True`) so JSON clients don't silently widen to IEEE 754.

The opening balance + signed `amount` columns (negative = outflow, positive = inflow) is summed with `SUM() OVER (...)`, never multiplied by a float.

## Consequences

**+** Exact arithmetic; reproducible across CI/local/prod.
**+** No silent precision loss when serializing to JSON.
**−** Slower than native float (roughly 50x), irrelevant at our volume.
**−** ORM annotations need `output_field=DecimalField(...)` explicitly when mixing.

## Alternatives

- **Integer cents.** Compact but loses currency exponent (some currencies use 3 decimals, e.g. KWD/BHD).
- **Float.** Disqualified by the context.
