# ADR-0003: Soft delete and an application audit log

**Status:** Accepted
**Date:** 2026-04-10

## Context

A finance ledger should not lose history. Users delete accounts, recategorize
transactions and edit budgets, and later it should still be possible to answer who
changed what and when, including for rows the user removed.

## Decision

1. **Soft delete.** Every user-owned model has `is_deleted` and `deleted_at`.
   `UserScopedModelViewSet` filters `is_deleted = false` and turns `DELETE` into a flag
   update. Deleting either leg of a transfer soft-deletes both. Uniqueness constraints and
   hot indexes are partial (`WHERE NOT is_deleted`), so deleted rows neither block names
   nor bloat indexes.
2. **Audit log.** `core.AuditLog` gets a row for every create, update and delete of
   accounts, categories, transactions and budgets, written by `pre_save` / `post_save` /
   `post_delete` receivers with JSON snapshots before and after. A soft delete is
   recorded as `delete`. The actor is a `ContextVar`: the API binds the authenticated user
   after DRF authentication, Celery tasks bind the user they act for, so service code
   does not pass `actor=` around. On PostgreSQL a row trigger makes the table
   append-only: `UPDATE` and `DELETE` fail, except the `ON DELETE SET NULL` of the actor.

## Consequences

**+** History survives deletes; restoring a row is clearing the flag.
**+** Audit completeness does not depend on each code path remembering to log.
**−** Every query must exclude deleted rows; this is centralized in the viewset mixin
and the owner-restricted querysets.
**−** `QuerySet.update()` and `bulk_create()` bypass signals and therefore the audit
log; they are not used on audited models.
**−** The trigger stops the application from rewriting history, but not the database
owner, which can truncate the table or drop the trigger.

## Alternatives

- **django-simple-history.** Full history tables per model: more storage and migrations
  than a who/what/when log needs.
- **Change data capture from the PostgreSQL WAL.** Complete, but heavy infrastructure for
  a single-instance project.
