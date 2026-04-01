"""Cashflow report: monthly income/expense/net for a user.

Reads from ``mv_monthly_cashflow`` so the dashboard is index-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import connection


@dataclass(frozen=True)
class CashflowRow:
    month: date
    currency: str
    income: Decimal
    expense: Decimal
    net: Decimal


SQL = """
SELECT month::date, currency, income, expense, net
FROM mv_monthly_cashflow
WHERE user_id = %(user_id)s
  AND month >= %(from_month)s
  AND month <  %(to_month)s
ORDER BY month, currency
"""


def cashflow_report(user_id: int, from_month: date, to_month: date) -> list[CashflowRow]:
    """Return rows from the cashflow MV in ``[from_month, to_month)``."""
    with connection.cursor() as cur:
        cur.execute(
            SQL,
            {"user_id": user_id, "from_month": from_month, "to_month": to_month},
        )
        rows = cur.fetchall()
    return [
        CashflowRow(month=r[0], currency=r[1], income=r[2], expense=r[3], net=r[4]) for r in rows
    ]
