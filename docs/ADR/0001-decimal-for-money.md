# ADR-0001: Decimal for money, never float

**Status:** Accepted
**Date:** 2026-04-10

## Context

Every amount in the ledger is money. Binary floating point cannot represent most decimal
fractions (`0.1 + 0.2 = 0.30000000000000004`), and the error accumulates across sums.

## Decision

Money is a decimal value end to end:

- Database: `NUMERIC(14, 2)` for amounts and limits, `NUMERIC(20, 10)` for FX rates;
  report aggregates are cast to `NUMERIC(18, 2)`.
- Models: `DecimalField`; Python code uses `decimal.Decimal`, never `float`.
- Converted amounts (cross-currency transfers) are quantized to cents explicitly.
- API: DRF keeps its default `COERCE_DECIMAL_TO_STRING`, so JSON carries `"12.50"`
  and clients do not silently widen to IEEE 754.
- Raw SQL that can come back as float on SQLite (window sums) is quantized back to cents.

Amounts are signed: negative is an outflow. Balances are sums of signed amounts plus the
account's opening balance.

## Consequences

**+** Exact arithmetic, the same results on PostgreSQL and SQLite.
**+** No precision loss when serializing to JSON.
**−** Decimal arithmetic is slower than float, irrelevant at this volume.
**−** Two decimal places fit most currencies but not the three-decimal ones (KWD, BHD).

## Alternatives

- **Integer minor units.** Compact and exact, but every boundary has to know the
  currency's exponent; `NUMERIC` keeps that out of the code.
- **Float.** Ruled out by the context.
