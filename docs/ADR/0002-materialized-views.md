# ADR-0002: Materialized views with concurrent refresh

**Status:** Accepted
**Date:** 2026-04-10

## Context

The cashflow, by-category and overruns reports aggregate every transaction in a date
window by month, category and currency. Computed per request, the cost grows with the
ledger. Reports are read far more often than they need to change, and monthly totals
can tolerate some staleness.

## Decision

Two materialized views, created by a PostgreSQL-only migration:

- `mv_monthly_category_totals(user_id, category_id, month, currency)`: expense totals.
- `mv_monthly_cashflow(user_id, month, currency)`: income, expense and net, excluding
  transfers.

Each has a unique index on its key, which `REFRESH MATERIALIZED VIEW CONCURRENTLY`
requires. The views are created `WITH NO DATA`; the refresh task populates an empty view
with a plain refresh and refreshes concurrently afterwards. A failed concurrent refresh
falls back to a blocking one so the view does not drift. Celery beat runs the task
hourly; `manage.py refresh_views` runs it on demand.

The migration checks `connection.vendor`, so the SQLite test database applies the same
migration chain without the views; tests that need them run on PostgreSQL.

## Consequences

**+** Reports read small pre-aggregated tables through their unique index.
**+** Concurrent refresh does not block report reads.
**−** Report data can be up to an hour old. `/budgets/{id}/status/` reads live data for
the one budget where freshness matters.
**−** Changing a view means a migration that drops and recreates it.

## Alternatives

- **Aggregate per request.** Simple, but the cost grows with history on every read.
- **Incremental summary tables maintained by triggers or signals.** Fresh, but couples
  every write to reporting.
- **Application cache (Redis).** Needs invalidation rules for every write path.
