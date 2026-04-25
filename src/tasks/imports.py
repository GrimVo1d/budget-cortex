"""CSV import processing tasks.

``parse_csv_import`` is the worker entry point: it reads the file behind a
:class:`CsvImport`, creates :class:`Transaction` rows with a per-line
``import_hash`` (the partial unique index ``tx_user_import_hash_unique``
makes re-runs idempotent) and always leaves the job ``done`` or ``failed``.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.core.audit import reset_actor, set_actor
from apps.imports.models import CsvImport, ImportStatus
from apps.imports.parsers import ImportFormatError, parse_file
from apps.imports.storage import resolve_stored
from apps.ledger.models import Transaction, TransactionType

logger = logging.getLogger(__name__)

_MAX_ERROR_LEN = 500


def _fail(job: CsvImport, message: str) -> dict[str, int]:
    job.status = ImportStatus.FAILED
    job.error = message[:_MAX_ERROR_LEN]
    job.save(update_fields=["status", "error", "updated_at"])
    return {"inserted": 0, "skipped": 0, "total": 0}


@shared_task(name="tasks.imports.parse_csv_import")
def parse_csv_import(import_id: int) -> dict[str, int]:
    job = CsvImport.objects.select_related("account").get(pk=import_id)
    if job.account.user_id != job.user_id or job.account.is_deleted:
        return _fail(job, "account is not available")

    job.status = ImportStatus.PARSING
    job.error = ""
    job.save(update_fields=["status", "error", "updated_at"])

    try:
        rows = list(parse_file(resolve_stored(job.file_path), job.fmt))
    except ImportFormatError as exc:
        logger.warning("csv_import_format_error", extra={"import_id": import_id})
        return _fail(job, str(exc))
    except (OSError, ValueError):
        logger.exception("csv_import_unreadable", extra={"import_id": import_id})
        return _fail(job, "uploaded file is not readable")

    expected = job.account.currency
    for r in rows:
        if r.currency is not None and r.currency != expected:
            return _fail(
                job, f"line {r.line}: currency {r.currency} does not match the account ({expected})"
            )

    inserted = 0
    # Rows are created on the owner's behalf, so the audit log names them.
    actor = set_actor(job.user_id)
    try:
        with transaction.atomic():
            for r in rows:
                _, created = Transaction.objects.get_or_create(
                    user_id=job.user_id,
                    import_hash=r.raw_hash,
                    defaults={
                        "account_id": job.account_id,
                        "occurred_at": r.occurred_at,
                        "amount": r.amount,
                        "currency": expected,
                        "type": TransactionType.REGULAR,
                        "description": r.description,
                    },
                )
                inserted += int(created)
    except Exception:
        logger.exception("csv_import_failed", extra={"import_id": import_id})
        return _fail(job, "import failed while saving transactions")
    finally:
        reset_actor(actor)

    job.status = ImportStatus.DONE
    job.rows_total = len(rows)
    job.rows_inserted = inserted
    job.rows_skipped = len(rows) - inserted
    job.save(update_fields=["status", "rows_total", "rows_inserted", "rows_skipped", "updated_at"])
    return {"inserted": inserted, "skipped": len(rows) - inserted, "total": len(rows)}


@shared_task(name="tasks.imports.cleanup_csv_files")
def cleanup_csv_files(older_than_days: int = 30, stale_pending_hours: int = 24) -> int:
    """Delete stored statements that are no longer needed.

    Files of finished (done/failed) jobs go after ``older_than_days``. A job
    still ``pending`` after ``stale_pending_hours`` was never picked up (lost
    message): it is failed and its file removed, so statements do not linger.
    """
    now = timezone.now()
    stale = CsvImport.objects.filter(
        status=ImportStatus.PENDING, created_at__lt=now - timedelta(hours=stale_pending_hours)
    )
    stale_ids = set()
    for job in stale.iterator():
        _fail(job, "the import was never processed; upload the file again")
        stale_ids.add(job.pk)

    cutoff = (now - timedelta(days=older_than_days)).timestamp()
    removed = 0
    finished = CsvImport.objects.filter(status__in=[ImportStatus.DONE, ImportStatus.FAILED])
    for job in finished.iterator():
        try:
            path: Path = resolve_stored(job.file_path)
            if path.exists() and (job.pk in stale_ids or path.stat().st_mtime < cutoff):
                path.unlink()
                removed += 1
        except (OSError, ValueError):
            logger.exception("csv_cleanup_failed", extra={"import_id": job.pk})
    return removed
