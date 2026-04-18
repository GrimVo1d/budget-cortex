# ADR-0004: Native currency per transaction, rates by date

**Status:** Accepted
**Date:** 2026-04-10

## Context

Accounts and transactions carry a currency (RUB, USD, EUR, …). Some features want
comparable numbers across currencies. The question is what to store and which rate to
use.

## Decision

- Store every amount in its **native** currency. Reports and budgets group by currency
  instead of mixing them.
- A cross-currency transfer takes the rate from the client and stores the converted,
  cent-quantized amount on the credit leg, so the rate actually used stays in the ledger.
- Rates are kept **per day** in `FxRate(base, quote, effective_on)`.
  `apps.fx.services.get_rate(base, quote, on)` looks in the Django cache (24 h), then the
  table, then the configured provider, whose answer is stored and cached. A cache outage
  degrades to database lookups; an unknown pair returns `None`.
- A daily beat task stores today's rate to `FX_BASE_CURRENCY` for every currency in use.
  Any future conversion uses the rate of the transaction's date, not of the query date.

## Consequences

**+** Historical numbers do not move when rates change.
**+** The native amount the user saw is never lost.
**−** No report converts between currencies yet; totals in several currencies are
reported side by side.
**−** Only the `stub` provider (fixed rates) ships; a real provider is one more class
behind `get_provider()`.

## Alternatives

- **Convert at query time with the current rate.** Past reports would change every day.
- **Store only converted amounts.** Loses the original amount and currency.
