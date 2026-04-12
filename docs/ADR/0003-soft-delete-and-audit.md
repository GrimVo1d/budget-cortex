# ADR-0003: Soft-delete + custom audit log

**Status:** Accepted
**Date:** 2026-04-10

## Context

A finance app cannot lose history. Users will delete accounts, recategorize transactions, edit budgets — and we need to be able to answer "who changed what, when" months later, including for entities the user "removed".

## Decision

Two complementary mechanisms:

1. **Soft delete.** Every mutable model has `is_deleted: bool` + `deleted_at: timestamptz`. Querysets expose `.alive()`; the user-scoped viewset mixin calls it automatically. `DELETE` endpoints flip the flag instead of issuing SQL `DELETE`.
2. **Audit log.** A single `audit_log` table receives a row for every create/update/delete of `Account`, `Transaction`, `Budget`, captured by Django `post_save`/`post_delete` signals. Actor attribution flows through a thread-local set by `AuditMiddleware` from `request.user.id`, so service code doesn't have to plumb `actor=` everywhere.

## Consequences

**+** History is preserved without trusting application code to remember.
**+** Restoring a "deleted" entity is `is_deleted=False`.
**+** Audit completeness doesn't depend on every service layer remembering to log.
**−** Foreign keys must respect `is_deleted` everywhere — encapsulated in querysets.
**−** Indexes need partial predicates (`WHERE is_deleted=false`) to stay compact.

## Alternatives

- **`django-simple-history`.** Stores entire row snapshots — heavy. We only need who/when/what-changed.
- **Hard delete + change-data-capture from PG WAL.** Overkill for a single-tenant pet project.
