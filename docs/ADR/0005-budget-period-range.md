# ADR-0005: Budget period as two timestamptz columns (with PG-only GIST overlap)

**Status:** Accepted
**Date:** 2026-04-10

## Context

A `Budget` covers a half-open period `[period_start, period_end)`. The hot query is *"does any active budget overlap with [a, b)?"* (overlapping budgets for the same category are a data error we want to detect). PostgreSQL has `tstzrange` + `&&` (overlap) backed by GIST. SQLite doesn't.

## Decision

Persist the range as **two `timestamptz` columns** `period_start` / `period_end` instead of `DateTimeRangeField`. On PostgreSQL, a follow-up migration adds a GIST index over `tstzrange(period_start, period_end)` so overlap queries are index-backed. On SQLite (tests on developer laptops) a plain partial B-tree index on `(period_start, period_end)` is the fallback — slower for overlaps but correct for the equality/range scans we have in tests.

The PG-only DDL goes through `RunPython` with `connection.vendor == 'postgresql'` so the same migration chain applies on both engines.

## Consequences

**+** Same model code, same migrations, two engines.
**+** GIST + `&&` on PG is index-only for overlap queries — exactly what the report needs.
**−** The fallback on SQLite cannot serve `&&` queries. We avoid those in tests by using equality filters.
**−** Application code must remember to filter `is_deleted=False` because the GIST index is partial.

## Alternatives

- **Native `DateTimeRangeField` everywhere.** Forces Postgres, blocks local SQLite testing.
- **One column with a duration.** Loses arbitrary endpoints; bad for custom-period budgets.
