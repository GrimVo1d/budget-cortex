"""CSV import task: formats, idempotency, failure handling."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from django.utils import timezone

from apps.core.models import AuditLog
from apps.imports.models import CsvImport, ImportFormat, ImportStatus
from apps.imports.storage import imports_root
from apps.ledger.models import Transaction
from tasks.imports import cleanup_csv_files, parse_csv_import
from tests.factories import make_account

pytestmark = pytest.mark.django_db


def _job(user: Any, account: Any, content: str, fmt: str = ImportFormat.GENERIC) -> CsvImport:
    root = imports_root()
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content.encode()).hexdigest()
    path = root / f"{digest}.csv"
    path.write_text(content, encoding="utf-8")
    return CsvImport.objects.create(
        user=user, account=account, fmt=fmt, file_path=str(path), file_hash=digest
    )


def test_generic_csv_inserts_rows(user: Any, account: Any) -> None:
    job = _job(
        user,
        account,
        "date,amount,currency,description\n"
        "2026-04-01T12:00:00,-100.50,RUB,Coffee\n"
        "2026-04-01T13:00:00,2500,RUB,Salary\n",
    )
    assert parse_csv_import(job.pk) == {"inserted": 2, "skipped": 0, "total": 2}
    job.refresh_from_db()
    assert job.status == ImportStatus.DONE


def test_missing_currency_falls_back_to_the_account(user: Any) -> None:
    usd = make_account(user, currency="USD")
    parse_csv_import(_job(user, usd, "date,amount\n2026-04-01,-5.00\n").pk)
    assert Transaction.objects.get(account=usd).currency == "USD"


def test_imported_rows_are_audited_as_the_owner(user: Any, account: Any) -> None:
    job = _job(user, account, "date,amount\n2026-04-01,-1.00\n")
    parse_csv_import(job.pk)
    [entry] = AuditLog.objects.filter(model="ledger.Transaction")
    assert entry.actor_id == user.pk


def test_reimport_is_idempotent(user: Any, account: Any) -> None:
    job = _job(user, account, "date,amount\n2026-04-01T12:00:00,-100.50\n")
    parse_csv_import(job.pk)
    assert parse_csv_import(job.pk) == {"inserted": 0, "skipped": 1, "total": 1}
    assert Transaction.objects.count() == 1


def test_identical_lines_are_both_kept(user: Any, account: Any) -> None:
    line = "2026-04-01T12:00:00,-3.00,RUB,Metro\n"
    job = _job(user, account, "date,amount,currency,description\n" + line + line)
    assert parse_csv_import(job.pk)["inserted"] == 2


def test_tinkoff_csv(user: Any, account: Any) -> None:
    job = _job(
        user,
        account,
        "Date;Amount;Currency;Description\n01.04.2026 12:00:00;-100,50;RUB;Coffee\n",
        ImportFormat.TINKOFF,
    )
    parse_csv_import(job.pk)
    assert Transaction.objects.get().amount == -100.50


@pytest.mark.parametrize(
    "content",
    [
        "date,amount\nnot-a-date,1\n",
        "date,amount,currency\n2026-04-01T12:00:00,1,RUBLES\n",
        "date,amount\n2026-04-01T12:00:00,abc\n",
        "nothing,useful\n1,2\n",
    ],
)
def test_bad_content_marks_job_failed(user: Any, account: Any, content: str) -> None:
    job = _job(user, account, content)
    parse_csv_import(job.pk)
    job.refresh_from_db()
    assert job.status == ImportStatus.FAILED
    assert job.error
    assert not Transaction.objects.exists()


def test_path_outside_imports_root_is_refused(user: Any, account: Any, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere.csv"
    outside.write_text("date,amount\n2026-04-01T12:00:00,1\n")
    job = CsvImport.objects.create(
        user=user, account=account, fmt="generic", file_path=str(outside), file_hash="x"
    )
    parse_csv_import(job.pk)
    job.refresh_from_db()
    assert job.status == ImportStatus.FAILED
    assert outside.exists()


def test_account_of_another_user_is_refused(user: Any, other_user: Any) -> None:
    job = _job(user, make_account(other_user), "date,amount\n2026-04-01T12:00:00,1\n")
    parse_csv_import(job.pk)
    job.refresh_from_db()
    assert job.status == ImportStatus.FAILED


def test_cleanup_fails_stale_pending_jobs_and_removes_files(user: Any, account: Any) -> None:
    job = _job(user, account, "date,amount\n2026-04-01,-1.00\n")
    CsvImport.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(days=2))
    assert cleanup_csv_files() == 1
    job.refresh_from_db()
    assert job.status == ImportStatus.FAILED
    assert not Path(job.file_path).exists()


def test_row_in_another_currency_fails_the_whole_job(user: Any, account: Any) -> None:
    content = "date,amount,currency\n2026-04-01,-5.00,RUB\n2026-04-02,-7.00,USD\n"
    parse_csv_import(_job(user, account, content).pk)
    job = CsvImport.objects.get()
    assert job.status == ImportStatus.FAILED
    assert job.error == "row 2: currency USD does not match the account (RUB)"
    assert not Transaction.objects.exists()
