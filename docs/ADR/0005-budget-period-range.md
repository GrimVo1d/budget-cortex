# ADR-0005: Budget period as two timestamps, overlap excluded on PostgreSQL

**Status:** Accepted
**Date:** 2026-04-10

## Context

A `Budget` covers the half-open period `[period_start, period_end)` for one category (or
all categories) and one currency. Two live budgets for the same user, category and
currency must not overlap, otherwise spending is counted against two limits. PostgreSQL
can enforce that with a range type and an exclusion constraint; SQLite, used by the
default test run, has neither.

## Decision

- Store the period as two `timestamptz` columns instead of `DateTimeRangeField`, so the
  model and migrations work on both engines.
- On PostgreSQL, migration `budgets.0002` enables `btree_gist` and adds:

  ```sql
  EXCLUDE USING gist (
      user_id WITH =, (COALESCE(category_id, 0)) WITH =, currency WITH =,
      tstzrange(period_start, period_end, '[)') WITH &&
  ) WHERE (NOT is_deleted)
  ```

  `COALESCE` makes all-category budgets (null category) collide with each other.
- The serializer performs the same overlap check with ordinary filters, so the API
  returns a validation error on both engines; the constraint covers concurrent writes.
- A partial B-tree on `(period_start, period_end)` serves range scans everywhere.

## Consequences

**+** One model, one migration chain, two engines.
**+** On PostgreSQL the invariant holds even under races between requests.
**−** The rule lives in two places (serializer and constraint) and has to stay in sync;
`tests/postgres` checks the constraint directly.
**−** A soft-deleted budget frees its period; restoring it can conflict.

## Alternatives

- **`DateTimeRangeField`.** Native range type, but PostgreSQL-only models block the SQLite
  test run.
- **Start plus duration.** Awkward for calendar months and custom periods.
- **Application check only.** Two concurrent requests could both pass it.
