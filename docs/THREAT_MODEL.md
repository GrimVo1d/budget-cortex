# THREAT_MODEL — budget-cortex

STRIDE for a single-tenant finance app. The most relevant categories here are Spoofing, Information disclosure (IDOR), and Tampering. SSRF and replay matter less because there are no outbound webhooks; the FX provider is the only external call and it's read-only.

## Trust boundary

```
[browser] ──TLS──> [ingress] ──> [API pod] ──> [Postgres]
                                  │
                                  ├──> [Redis (cache, ratelimit-tbd)]
                                  ├──> [Worker pod] ──> [FX provider HTTPS] (read-only)
                                  └──> [Beat pod]
```

## Threats and mitigations

| ID | STRIDE | Scenario | Mitigation |
|---|---|---|---|
| T-01 | **S** | Stolen JWT used to act as another user | Short access TTL (15 min), refresh rotation. Argon2 password hashing. |
| T-02 | **T** | User edits past transactions without trace | `audit_log` row on every create/update/delete via signals + `AuditMiddleware` thread-local actor. |
| T-03 | **I** (IDOR) | User A requests `/accounts/<B's id>/` | `UserScopedModelViewSet.get_queryset()` filters every queryset by `user_id=request.user.id` and `.alive()`. Returning 404 (not 403) avoids leaking existence. |
| T-04 | **I** | Listing other people's transactions via the budget status endpoint | The status filter is `Q(user_id=request.user.id, ...)` — cross-user category ids return empty aggregates. |
| T-05 | **I** | Listing soft-deleted rows by tweaking query params | All querysets pass through `.alive()`; the deleted flag is not exposed in filterset fields. |
| T-06 | **T** | CSV import injects pre-dated transactions to backdate budgets | Each row's `import_hash` is stored unique-per-user; replays are no-ops. The budget overrun report uses the materialized view which itself is built from `is_deleted=false` rows. |
| T-07 | **D** (DoS) | Huge CSV import file | Celery task processes row-by-row inside one `transaction.atomic`; size cap belongs at the ingress (TODO documented). |
| T-08 | **I** | Audit log itself leaks data via API | The model has no viewset. Admin-only access. |
| T-09 | **T** | Money loss through a non-atomic cross-account transfer | `apps.ledger.services.create_transfer` runs inside `transaction.atomic`; cross-currency requires an explicit `fx_rate`. |
| T-10 | **I** | FX rate poisoning by a compromised provider produces fake reports | `get_rate` caches the last DB value; manual override possible via admin. Documented in RUNBOOK. |
| T-11 | **E** (EoP) | Privilege escalation via an admin-only endpoint | DRF default permission is `IsAuthenticated`; admin endpoints are staff-gated. |

## Residual risks

1. **Compromised user password** → full access to that user's ledger. Out of scope for app-side mitigation; rely on argon2 + rate-limit on auth (TODO).
2. **DB exfiltration** → all amounts plain. Encryption at rest is an infra concern. PII inside transaction descriptions is per-user; advise users not to paste card numbers there (admin-facing warning is TODO).

## Pre-prod checklist

- [ ] JWT signing key replaced from default.
- [ ] Argon2 used as the password hasher (already in settings).
- [ ] Postgres backups configured (PITR + 14d retention).
- [ ] Audit log retention defined (default: indefinite; document trim policy).
- [ ] Rate-limit on `POST /auth/token/` (TODO).
