# PERFORMANCE — budget-cortex

Targets and capacity math for the analytics-heavy paths. Capacity is set by Postgres query latency, not by Django request overhead.

## SLO

| Metric | Target |
|---|---|
| `GET /transactions/` (page 50, includes running balance) P95 | < 80 ms |
| `GET /reports/cashflow/` P95 | < 50 ms |
| `GET /reports/by-category/` P95 | < 80 ms (recursive CTE rollup) |
| `GET /budgets/<id>/status/` P95 | < 100 ms |
| MV staleness | ≤ 1 hour (refresh cadence) |

## Hot queries and indexes

| Query | Index used | Expected cost |
|---|---|---|
| Transactions list, ordered by occurred_at | `tx_user_occurred_at_idx` (partial, `WHERE is_deleted=false`) | Index Scan |
| Running balance OVER (PARTITION BY account_id ORDER BY occurred_at, id) | same partial index | WindowAgg |
| Idempotent CSV import lookup | `tx_user_import_hash_unique` (partial unique on `import_hash IS NOT NULL`) | unique index hit |
| Cashflow report read | `mv_monthly_cashflow_uniq (user_id, month, currency)` | Index Only Scan |
| By-category report read | recursive CTE on `ledger_category` + `mv_monthly_category_totals_uniq` | nested loop / hash join |
| Budget overruns | join MV against `budgets_budget` with month range | aggregate over MV |
| Historic occurred_at scans (1+ year) | `tx_occurred_at_brin` | BRIN scan |

### `EXPLAIN ANALYZE` shapes to expect

Running balance:
```
WindowAgg
  -> Sort (occurred_at, id)
       -> Index Scan using tx_user_occurred_at_idx on ledger_transaction
            Index Cond: (user_id = $1)
```

Cashflow report:
```
Index Only Scan using mv_monthly_cashflow_uniq on mv_monthly_cashflow
  Index Cond: ((user_id = $1) AND (month >= $2) AND (month < $3))
Execution Time: < 1 ms
```

If you see `Seq Scan` on `ledger_transaction` for any report — the MV refresh task probably failed. Check `tasks.analytics.refresh_materialized_views` logs.

## BRIN sizing

BRIN tunable `pages_per_range = 32` is a deliberate trade: smaller ranges = more precision = more disk; larger ranges = less precision = fewer pages skipped. At 32, on a table where transactions arrive roughly in order, the index is ~1000× smaller than B-tree on `occurred_at`, and full-month scans are still index-driven.

## Capacity math (single node 4 CPU / 8 GB)

```
T_req ≈ T_django + T_pg_query + T_serialize
      ≈ 5ms + 8ms (index hit) + 3ms = 16ms
```

With 4 sync gunicorn workers: ~250 RPS per node. Reports are heavier (~50ms) but rate-limited by usage pattern, not by Django.

PG connections: 4 workers × 1 conn/req + 2 worker pods × concurrency 4 = ~20 conns/node. PG default `max_connections=100` → 5 nodes ceiling without pgbouncer.

## Scaling checklist

1. **pgbouncer** in front of PG once you exceed 5 nodes.
2. **Lower MV refresh interval** to 15 minutes if users notice 1h staleness; cost is the lock contention window.
3. **Partition `ledger_transaction`** by `occurred_at` monthly once the table crosses 50M rows. The BRIN index becomes per-partition automatically.
4. **Read replicas** for report endpoints. Reports are read-only and can tolerate replica lag (the MV itself is already lagging).
5. **Async DRF views** for reports — only worth it past 500 RPS/node and requires asyncpg.

## What we deliberately don't optimize

- Template render / serializer overhead — Django default is fine.
- DB connection pooling in app — PG `CONN_MAX_AGE>0` is enough up to single-digit nodes.
- Caching individual transactions in Redis — they're already index hits, and invalidation costs more than the lookup.
