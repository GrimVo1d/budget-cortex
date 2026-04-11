"""Materialized views for spending analytics.

Two MVs, both with unique indexes so ``REFRESH MATERIALIZED VIEW CONCURRENTLY``
can be used (no read-side locking on dashboards during refresh).

- ``mv_monthly_category_totals`` — sum of expense amounts per
  (user, category, month), in transaction's native currency.
- ``mv_monthly_cashflow`` — net cashflow per (user, month): income minus
  expense; transfers excluded.

PostgreSQL-only. SQLite test runs apply these in test DBs that target PG.
"""

from __future__ import annotations

from django.db import migrations

MV_CATEGORY_TOTALS = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_category_totals AS
SELECT
    t.user_id,
    t.category_id,
    date_trunc('month', t.occurred_at) AS month,
    t.currency,
    SUM(ABS(t.amount))::numeric(18, 2) AS total_expense,
    COUNT(*)                            AS tx_count
FROM ledger_transaction t
JOIN ledger_category c ON c.id = t.category_id
WHERE t.is_deleted = false
  AND c.kind = 'expense'
GROUP BY t.user_id, t.category_id, date_trunc('month', t.occurred_at), t.currency
WITH NO DATA;
"""

MV_CASHFLOW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_cashflow AS
SELECT
    t.user_id,
    date_trunc('month', t.occurred_at) AS month,
    t.currency,
    SUM(CASE WHEN c.kind = 'income'  THEN t.amount      ELSE 0 END)::numeric(18, 2) AS income,
    SUM(CASE WHEN c.kind = 'expense' THEN ABS(t.amount) ELSE 0 END)::numeric(18, 2) AS expense,
    SUM(CASE WHEN c.kind = 'income'  THEN t.amount
             WHEN c.kind = 'expense' THEN -ABS(t.amount)
             ELSE 0 END)::numeric(18, 2) AS net
FROM ledger_transaction t
JOIN ledger_category c ON c.id = t.category_id
WHERE t.is_deleted = false
GROUP BY t.user_id, date_trunc('month', t.occurred_at), t.currency
WITH NO DATA;
"""

IDX_CATEGORY = """
CREATE UNIQUE INDEX IF NOT EXISTS mv_monthly_category_totals_uniq
ON mv_monthly_category_totals (user_id, category_id, month, currency);
"""

IDX_CASHFLOW = """
CREATE UNIQUE INDEX IF NOT EXISTS mv_monthly_cashflow_uniq
ON mv_monthly_cashflow (user_id, month, currency);
"""


def _pg_only(sql: str, reverse_sql: str):  # type: ignore[no-untyped-def]
    def forward(apps, schema_editor):  # type: ignore[no-untyped-def]
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(sql)

    def reverse(apps, schema_editor):  # type: ignore[no-untyped-def]
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(reverse_sql)

    return migrations.RunPython(forward, reverse)


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0004_transaction_brin_occurred_at"),
    ]

    operations = [
        _pg_only(MV_CATEGORY_TOTALS, "DROP MATERIALIZED VIEW IF EXISTS mv_monthly_category_totals;"),
        _pg_only(IDX_CATEGORY, "DROP INDEX IF EXISTS mv_monthly_category_totals_uniq;"),
        _pg_only(MV_CASHFLOW, "DROP MATERIALIZED VIEW IF EXISTS mv_monthly_cashflow;"),
        _pg_only(IDX_CASHFLOW, "DROP INDEX IF EXISTS mv_monthly_cashflow_uniq;"),
    ]
