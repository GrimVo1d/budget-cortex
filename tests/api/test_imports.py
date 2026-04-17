from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.imports import views
from apps.imports.models import CsvImport, ImportStatus
from apps.ledger.models import Transaction
from tests.factories import make_account

pytestmark = pytest.mark.django_db

IMPORTS = "/api/v1/imports/"
CSV = b"date,amount,currency,description\n2026-04-01T12:00:00,-100.50,RUB,Coffee\n"


def _upload(client: APIClient, account_id: int, content: bytes = CSV, fmt: str = "generic") -> Any:
    file = SimpleUploadedFile("statement.csv", content, content_type="text/csv")
    return client.post(
        IMPORTS, {"account": account_id, "fmt": fmt, "file": file}, format="multipart"
    )


def test_upload_runs_import(
    client: APIClient, account: Any, django_capture_on_commit_callbacks: Any
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        resp = _upload(client, account.pk)

    assert resp.status_code == 202
    job = client.get(f"{IMPORTS}{resp.json()['id']}/").json()
    assert job["status"] == ImportStatus.DONE
    assert job["rows_inserted"] == 1
    assert "file_path" not in job
    assert Transaction.objects.get().description == "Coffee"


def test_same_file_twice_is_conflict(client: APIClient, account: Any) -> None:
    assert _upload(client, account.pk).status_code == 202
    second = _upload(client, account.pk)
    assert second.status_code == 409
    assert second.json()["code"] == "duplicate_file"


def test_oversized_file_is_rejected(client: APIClient, account: Any, settings: Any) -> None:
    settings.IMPORT_MAX_BYTES = 10
    resp = _upload(client, account.pk)
    assert resp.status_code == 413
    assert not CsvImport.objects.exists()


def test_foreign_account_is_rejected(client: APIClient, other_user: Any) -> None:
    resp = _upload(client, make_account(other_user).pk)
    assert resp.status_code == 400


def test_jobs_are_user_scoped(client: APIClient, account: Any, other_user: Any) -> None:
    job_id = _upload(client, account.pk).json()["id"]
    intruder = APIClient()
    intruder.force_authenticate(other_user)
    assert intruder.get(f"{IMPORTS}{job_id}/").status_code == 404
    assert intruder.get(IMPORTS).json()["count"] == 0


def test_oversized_request_is_refused_before_parsing(
    client: APIClient, account: Any, settings: Any
) -> None:
    settings.IMPORT_MAX_BYTES = 10
    resp = _upload(client, account.pk, content=b"x" * 100_000)
    assert resp.status_code == 413
    assert resp.json()["code"] == "file_too_large"


@pytest.mark.django_db(transaction=True)
def test_broker_outage_fails_the_job_and_allows_retry(
    client: APIClient, account: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # transaction=True: outside a test transaction on_commit fires at once,
    # exactly like the autocommit view in production.
    def broker_down(*args: Any, **kwargs: Any) -> None:
        raise ConnectionError("broker unreachable")

    with monkeypatch.context() as m:
        m.setattr(views.parse_csv_import, "delay", broker_down)
        resp = _upload(client, account.pk)
    assert resp.status_code == 503
    assert resp.json()["code"] == "queue_unavailable"
    job = CsvImport.objects.get()
    assert job.status == ImportStatus.FAILED
    assert not Path(job.file_path).exists()

    retry = _upload(client, account.pk)
    assert retry.status_code == 202
    assert retry.json()["id"] == job.pk
    assert retry.json()["status"] == ImportStatus.DONE
