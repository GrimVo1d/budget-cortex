"""Celery tasks that maintain analytics materialized views."""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import connection

logger = logging.getLogger(__name__)

MATERIALIZED_VIEWS = (
    "mv_monthly_category_totals",
    "mv_monthly_cashflow",
)


@shared_task(
    name="tasks.analytics.refresh_materialized_views",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def refresh_materialized_views(self) -> dict[str, str]:  # type: ignore[no-untyped-def]
    """Run ``REFRESH MATERIALIZED VIEW CONCURRENTLY`` on each MV.

    CONCURRENTLY needs a unique index on each MV (provided by the
    initial migration) and skips the AccessExclusiveLock that would
    block dashboards mid-refresh.
    """
    results: dict[str, str] = {}
    with connection.cursor() as cur:
        for mv in MATERIALIZED_VIEWS:
            try:
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}")
                results[mv] = "ok"
            except Exception:
                logger.exception("mv_refresh_failed", extra={"mv": mv})
                cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
                results[mv] = "ok-non-concurrent"
    return results
