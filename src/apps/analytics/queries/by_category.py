"""Spending by category (with recursive parent rollup).

Uses a recursive CTE to roll child-category totals up to roots so the
report can be viewed at either the root or leaf level. Source rows come
from ``mv_monthly_category_totals``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import connection


@dataclass(frozen=True)
class CategoryRow:
    category_id: int
    category_name: str
    root_id: int
    root_name: str
    currency: str
    total_expense: Decimal


SQL = """
WITH RECURSIVE roots(id, root_id) AS (
    SELECT c.id, c.id
    FROM ledger_category c
    WHERE c.parent_id IS NULL AND c.user_id = %(user_id)s
  UNION ALL
    SELECT c.id, r.root_id
    FROM ledger_category c
    JOIN roots r ON c.parent_id = r.id
    WHERE c.user_id = %(user_id)s
)
SELECT
    mv.category_id,
    c.name,
    r.root_id,
    cr.name AS root_name,
    mv.currency,
    SUM(mv.total_expense)::numeric(18, 2) AS total_expense
FROM mv_monthly_category_totals mv
JOIN roots r            ON r.id = mv.category_id
JOIN ledger_category c  ON c.id = mv.category_id
JOIN ledger_category cr ON cr.id = r.root_id
WHERE mv.user_id = %(user_id)s
  AND mv.month >= %(from_month)s
  AND mv.month <  %(to_month)s
GROUP BY mv.category_id, c.name, r.root_id, cr.name, mv.currency
ORDER BY total_expense DESC
"""


def by_category_report(user_id: int, from_month: date, to_month: date) -> list[CategoryRow]:
    with connection.cursor() as cur:
        cur.execute(
            SQL,
            {"user_id": user_id, "from_month": from_month, "to_month": to_month},
        )
        rows = cur.fetchall()
    return [
        CategoryRow(
            category_id=r[0],
            category_name=r[1],
            root_id=r[2],
            root_name=r[3],
            currency=r[4],
            total_expense=r[5],
        )
        for r in rows
    ]
