"""End-to-end CSV import scenarios.

Covers the three supported formats and the idempotency guarantee: parsing
the same file twice never produces duplicate transactions.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from apps.imports.models import CsvImport, ImportFormat, ImportStatus
from apps.ledger.models import Transaction
from tasks.imports import parse_csv_import


def _write_csv(tmp_path: Path, name: str, content: str) -> tuple[str, str]:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return str(path), digest


@pytest.mark.django_db
def test_parse_generic_csv_inserts_rows(tmp_path, user, account):  # type: ignore[no-untyped-def]
    csv = (
        "date,amount,currency,description\n"
        "2026-04-01T12:00:00,-100.50,RUB,Coffee\n"
        "2026-04-01T13:00:00,2500,RUB,Salary\n"
    )
    path, digest = _write_csv(tmp_path, "g.csv", csv)
    job = CsvImport.objects.create(
        user=user, account=account, fmt=ImportFormat.GENERIC, file_path=path, file_hash=digest
    )

    result = parse_csv_import(job.id)

    job.refresh_from_db()
    assert result == {"inserted": 2, "skipped": 0, "total": 2}
    assert job.status == ImportStatus.DONE
    assert Transaction.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_parse_csv_is_idempotent(tmp_path, user, account):  # type: ignore[no-untyped-def]
    csv = "date,amount,currency,description\n2026-04-01T12:00:00,-100.50,RUB,Coffee\n"
    path, digest = _write_csv(tmp_path, "g.csv", csv)
    job = CsvImport.objects.create(
        user=user, account=account, fmt=ImportFormat.GENERIC, file_path=path, file_hash=digest
    )

    parse_csv_import(job.id)
    second = parse_csv_import(job.id)

    assert second == {"inserted": 0, "skipped": 1, "total": 1}
    assert Transaction.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_parse_tinkoff_csv(tmp_path, user, account):  # type: ignore[no-untyped-def]
    csv = "Date;Amount;Currency;Description\n01.04.2026 12:00:00;-100,50;RUB;Coffee\n"
    path, digest = _write_csv(tmp_path, "t.csv", csv)
    job = CsvImport.objects.create(
        user=user, account=account, fmt=ImportFormat.TINKOFF, file_path=path, file_hash=digest
    )

    parse_csv_import(job.id)

    assert Transaction.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_parse_failure_marks_job_failed(tmp_path, user, account):  # type: ignore[no-untyped-def]
    csv = "date,amount\nnot-a-date,xxx\n"
    path, digest = _write_csv(tmp_path, "bad.csv", csv)
    job = CsvImport.objects.create(
        user=user, account=account, fmt=ImportFormat.GENERIC, file_path=path, file_hash=digest
    )

    parse_csv_import(job.id)

    job.refresh_from_db()
    assert job.status == ImportStatus.FAILED
    assert job.error
