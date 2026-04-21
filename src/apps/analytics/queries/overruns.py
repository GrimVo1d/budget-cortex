"""Budget overruns report: budgets where spending exceeded the limit.

Joins ``budgets_budget`` against ``mv_monthly_category_totals`` to compute
spend per budget period and surface only the ones where ``spent > limit``.
A category budget also counts its child categories, like the live
``/budgets/{id}/status/`` endpoint. The MV is monthly: every month that
overlaps the budget period counts in full, so the report is exact for
month-aligned budgets; ``status`` is the precise per-budget view.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import connection


@dataclass(frozen=True)
class OverrunRow:
    budget_id: int
    category_id: int | None
    currency: str
    limit_amount: Decimal
    spent_amount: Decimal
    overrun_pct: Decimal | None  # spent as a percentage of the limit; None for a zero limit


SQL = """
WITH spent AS (
    SELECT
        b.id                 AS budget_id,
        b.category_id,
        b.currency,
        b.limit_amount,
        COALESCE(SUM(mv.total_expense), 0)::numeric(18, 2) AS spent_amount
    FROM budgets_budget b
    LEFT JOIN (
        mv_monthly_category_totals mv
        JOIN ledger_category c ON c.id = mv.category_id
    )
      ON mv.user_id   = b.user_id
     AND mv.currency  = b.currency
     AND mv.month    >= date_trunc('month', b.period_start)
     AND mv.month    <  b.period_end
     AND (b.category_id IS NULL OR b.category_id IN (c.id, c.parent_id))
    WHERE b.user_id    = %(user_id)s
      AND b.is_deleted = false
    GROUP BY b.id, b.category_id, b.currency, b.limit_amount
)
SELECT
    budget_id,
    category_id,
    currency,
    limit_amount,
    spent_amount,
    round(spent_amount * 100 / NULLIF(limit_amount, 0), 2) AS overrun_pct
FROM spent
WHERE spent_amount > limit_amount
ORDER BY (spent_amount - limit_amount) DESC
"""


def overruns_report(user_id: int) -> list[OverrunRow]:
    with connection.cursor() as cur:
        cur.execute(SQL, {"user_id": user_id})
        rows = cur.fetchall()
    return [
        OverrunRow(
            budget_id=r[0],
            category_id=r[1],
            currency=r[2],
            limit_amount=r[3],
            spent_amount=r[4],
            overrun_pct=r[5],
        )
        for r in rows
    ]
