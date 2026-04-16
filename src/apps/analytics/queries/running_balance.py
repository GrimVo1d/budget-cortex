"""Raw-SQL running balance via window function.

Uses ``SUM(amount) OVER (PARTITION BY account_id ORDER BY occurred_at, id)``
which is portable between PostgreSQL (16+) and SQLite (3.25+). The function
returns the cumulative sum **excluding** the account's opening balance — the
list endpoint combines them at response time so the on-the-wire value matches
what the user sees in their account.

We compute over the user's full ledger (filtered by ``is_deleted=false``)
and then narrow to the requested ids; this keeps the window-frame consistent
regardless of page boundaries or active filters.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from django.db import connection

_CENT = Decimal("0.01")


def running_balances_for(ids: Sequence[int], user_id: int) -> dict[int, Decimal]:
    """Return ``{tx_id: cumulative_balance_excluding_opening_balance}``."""
    if not ids:
        return {}
    placeholders = ",".join(["%s"] * len(ids))
    # Only "%s" placeholders are interpolated; values go through params.
    sql = f"""
        WITH ledger AS (
            SELECT id,
                   SUM(amount) OVER (
                       PARTITION BY account_id
                       ORDER BY occurred_at, id
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                   ) AS running
            FROM ledger_transaction
            WHERE user_id = %s AND is_deleted = %s
        )
        SELECT id, running FROM ledger WHERE id IN ({placeholders})
    """  # noqa: S608
    with connection.cursor() as cur:
        cur.execute(sql, [user_id, False, *ids])
        # SQLite's SUM() over decimals yields a float; quantize back to cents.
        return {int(row[0]): Decimal(str(row[1])).quantize(_CENT) for row in cur.fetchall()}
