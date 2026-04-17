"""Error bodies keep the {"code", "detail"} shape, database errors included."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from django.db import DataError, IntegrityError
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.core.exceptions import exception_handler
from apps.core.logging import JsonFormatter

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [(IntegrityError("dup"), 409, "conflict"), (DataError("overflow"), 400, "invalid_value")],
)
def test_database_errors_are_mapped(exc: Exception, status: int, code: str) -> None:
    resp = exception_handler(exc, {})
    assert resp is not None
    assert resp.status_code == status
    assert resp.data["code"] == code


@pytest.mark.parametrize("month", ["2026-1", "26-01", "2026-13", "2026-01-01"])
def test_report_months_must_be_yyyy_mm(client: APIClient, month: str) -> None:
    resp = client.get("/api/v1/reports/cashflow/", {"from": month, "to": "2026-12"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_month"


def test_json_log_keeps_path_but_not_query_string() -> None:
    request = RequestFactory().get("/api/v1/transactions/", {"q": "salary"})
    record = logging.makeLogRecord(
        {"msg": "Bad Request", "levelname": "WARNING", "request": request, "status_code": 400}
    )
    payload: dict[str, Any] = json.loads(JsonFormatter().format(record))
    assert payload["path"] == "/api/v1/transactions/"
    assert "salary" not in json.dumps(payload)
