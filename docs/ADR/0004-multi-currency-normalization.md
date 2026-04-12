# ADR-0004: Multi-currency normalization at occurrence time

**Status:** Accepted
**Date:** 2026-04-10

## Context

Transactions carry their native currency (RUB, USD, EUR, ...). Reports and budgets often need a single comparable amount. The question is *when* to apply the FX rate.

## Decision

Store amounts in their **native** currency on `Transaction`. Whenever we need a normalized value, look up the FX rate **at `occurred_at`**, not at query time:

```python
rate = get_rate(base=tx.currency, quote="RUB", on=tx.occurred_at.date())
normalized = tx.amount * rate
```

`apps.fx.services.get_rate` checks Redis (24h TTL) → DB (`FxRate(base, quote, effective_on)`) → provider. The provider abstraction has a `stub` and is wired to swap for a real one. Cache failures fall back to DB; provider failures fall back to the most recent DB rate.

## Consequences

**+** Historical reports are deterministic. Re-running a "2026-01 cashflow" tomorrow returns the same number as today, regardless of FX moves.
**+** Cross-currency transfers persist their FX rate at the moment of the transfer; same logic.
**−** A grace period is needed for the FX provider to publish today's rate before today's reports stabilize. Documented in RUNBOOK.

## Alternatives

- **Apply current rate at query time.** Historical reports would shift retroactively — confusing for users and unauditable.
- **Store only normalized amounts.** Loses information; can't render the native amount as the user saw it.
