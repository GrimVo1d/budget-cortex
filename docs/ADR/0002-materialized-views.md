# ADR-0002: Materialized views with CONCURRENTLY refresh

**Status:** Accepted
**Date:** 2026-04-10

## Context

Two reports (`cashflow`, `by-category`) and the overruns endpoint scan every transaction in a date window grouped by month + category + currency. On a 10M-row table the on-the-fly aggregation costs hundreds of milliseconds per request. Reports are read at orders-of-magnitude higher rate than transactions are written, so caching the aggregate makes sense.

## Decision

Two materialized views maintained by Celery beat:

- `mv_monthly_category_totals(user_id, category_id, month, currency)`
- `mv_monthly_cashflow(user_id, month, currency)` with income/expense/net columns

Both carry a unique index over the grouping key, which is what `REFRESH MATERIALIZED VIEW CONCURRENTLY` requires. Refresh runs hourly. On failure (most often lock contention) the task falls back to a blocking refresh so the view doesn't drift.

The migration is gated to PostgreSQL only (RunPython with `connection.vendor` check); SQLite test runs skip it.

## Consequences

**+** Reports become index-only scans, sub-millisecond.
**+** `CONCURRENTLY` avoids the AccessExclusiveLock that would block dashboards mid-refresh.
**−** Up-to-one-hour staleness on reports. Acceptable for monthly-aggregate use cases; documented in RUNBOOK.
**−** MVs cannot be transactional. We accept that and refresh after the fact.

## Alternatives

- **Plain aggregation per request.** Works at small scale, doesn't at 10M+ rows.
- **Eager incremental updates** via signal/triggers. Plausible but couples writes to reporting concerns; reject for now.
- **External cache (Redis/memcached).** Adds invalidation logic. The MV is simpler.
