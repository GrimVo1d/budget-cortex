"""CSV import processing tasks.

``parse_csv_import`` is the main worker entry point: it reads the file
pointed to by :class:`CsvImport`, iterates parsed rows, and creates
:class:`Transaction` records with a per-row ``import_hash`` to make
re-runs idempotent (the partial unique index in 0003 enforces it).
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from celery import shared_task
from django.db import transaction

from apps.imports.models import CsvImport, ImportStatus
from apps.imports.parsers import ImportFormatError, parse_file
from apps.ledger.models import Transaction, TransactionType

logger = logging.getLogger(__name__)


@shared_task(
    name="tasks.imports.parse_csv_import",
    bind=True,
    autoretry_for=(OSError,),
    retry_backoff=15,
    retry_backoff_max=300,
    max_retries=3,
)
def parse_csv_import(self, import_id: int) -> dict[str, int]:  # type: ignore[no-untyped-def]
    job: CsvImport = CsvImport.objects.select_related("account").get(pk=import_id)
    job.status = ImportStatus.PARSING
    job.save(update_fields=["status", "updated_at"])

    inserted = 0
    skipped = 0
    total = 0
    try:
        rows = list(parse_file(job.file_path, job.fmt))
    except ImportFormatError as exc:
        job.status = ImportStatus.FAILED
        job.error = str(exc)
        job.save(update_fields=["status", "error", "updated_at"])
        logger.warning("csv_import_format_error", extra={"import_id": import_id})
        return {"inserted": 0, "skipped": 0, "total": 0}

    total = len(rows)
    with transaction.atomic():
        for r in rows:
            tx_type = TransactionType.EXPENSE if r.amount < 0 else TransactionType.INCOME
            _, created = Transaction.objects.get_or_create(
                user_id=job.user_id,
                import_hash=r.raw_hash,
                defaults={
                    "account_id": job.account_id,
                    "occurred_at": r.occurred_at,
                    "amount": r.amount,
                    "currency": r.currency,
                    "type": tx_type,
                    "description": r.description,
                },
            )
            if created:
                inserted += 1
            else:
                skipped += 1

    job.status = ImportStatus.DONE
    job.rows_total = total
    job.rows_inserted = inserted
    job.rows_skipped = skipped
    job.save(update_fields=["status", "rows_total", "rows_inserted", "rows_skipped", "updated_at"])
    return {"inserted": inserted, "skipped": skipped, "total": total}


@shared_task(name="tasks.imports.cleanup_csv_files")
def cleanup_csv_files(older_than_days: int = 30) -> int:
    """Drop staged CSV files older than N days for ``done``/``failed`` jobs."""
    cutoff = time.time() - older_than_days * 86400
    removed = 0
    for job in CsvImport.objects.filter(
        status__in=[ImportStatus.DONE, ImportStatus.FAILED]
    ).iterator():
        path = Path(job.file_path)
        try:
            if path.exists() and path.stat().st_mtime < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            logger.exception("csv_cleanup_failed", extra={"path": str(path)})
    return removed
