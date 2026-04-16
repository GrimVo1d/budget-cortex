"""Celery tasks that maintain analytics materialized views."""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import connection
from django.db.backends.utils import CursorWrapper

logger = logging.getLogger(__name__)

MATERIALIZED_VIEWS = (
    "mv_monthly_category_totals",
    "mv_monthly_cashflow",
)


def _is_populated(cur: CursorWrapper, view: str) -> bool:
    cur.execute("SELECT relispopulated FROM pg_class WHERE relname = %s", [view])
    row = cur.fetchone()
    return bool(row and row[0])


@shared_task(
    name="tasks.analytics.refresh_materialized_views",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def refresh_materialized_views() -> dict[str, str]:
    """Refresh every analytics MV.

    ``CONCURRENTLY`` (possible thanks to the unique index on each MV) avoids
    the AccessExclusiveLock that would block report reads mid-refresh. It is
    not allowed on a never-populated view (the migration creates them
    ``WITH NO DATA``), and if it fails for another reason we fall back to a
    blocking refresh so the data does not drift.
    """
    results: dict[str, str] = {}
    with connection.cursor() as cur:
        for mv in MATERIALIZED_VIEWS:
            if not _is_populated(cur, mv):
                cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
                results[mv] = "populated"
                continue
            try:
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}")
                results[mv] = "ok"
            except Exception:
                logger.exception("mv_refresh_failed", extra={"mv": mv})
                cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
                results[mv] = "ok-non-concurrent"
    return results
