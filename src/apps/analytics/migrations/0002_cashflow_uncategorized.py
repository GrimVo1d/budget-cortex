"""Count uncategorized transactions in ``mv_monthly_cashflow``.

The first version inner-joined categories, so anything without a category
(every row coming from a CSV import) was invisible in the cashflow report.
Now the category kind decides when there is one, the sign of the amount
otherwise; transfer legs stay out explicitly. PostgreSQL-only.
"""

from __future__ import annotations

from django.db import migrations

MV_CASHFLOW_V1 = """
CREATE MATERIALIZED VIEW mv_monthly_cashflow AS
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

MV_CASHFLOW_V2 = """
CREATE MATERIALIZED VIEW mv_monthly_cashflow AS
WITH classified AS (
    SELECT
        t.user_id,
        date_trunc('month', t.occurred_at) AS month,
        t.currency,
        t.amount,
        COALESCE(c.kind, CASE WHEN t.amount >= 0 THEN 'income' ELSE 'expense' END) AS kind
    FROM ledger_transaction t
    LEFT JOIN ledger_category c ON c.id = t.category_id
    WHERE t.is_deleted = false
      AND t.type <> 'transfer'
)
SELECT
    user_id,
    month,
    currency,
    SUM(CASE WHEN kind = 'income'  THEN amount      ELSE 0 END)::numeric(18, 2) AS income,
    SUM(CASE WHEN kind = 'expense' THEN ABS(amount) ELSE 0 END)::numeric(18, 2) AS expense,
    SUM(CASE WHEN kind = 'income'  THEN amount ELSE -ABS(amount) END)::numeric(18, 2) AS net
FROM classified
GROUP BY user_id, month, currency
WITH NO DATA;
"""

IDX_CASHFLOW = """
CREATE UNIQUE INDEX mv_monthly_cashflow_uniq
ON mv_monthly_cashflow (user_id, month, currency);
"""


def _replace(sql: str):  # type: ignore[no-untyped-def]
    def run(apps, schema_editor):  # type: ignore[no-untyped-def]
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute("DROP MATERIALIZED VIEW IF EXISTS mv_monthly_cashflow;")
            schema_editor.execute(sql)
            schema_editor.execute(IDX_CASHFLOW)

    return run


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0001_materialized_views"),
    ]

    operations = [
        migrations.RunPython(_replace(MV_CASHFLOW_V2), _replace(MV_CASHFLOW_V1)),
    ]
