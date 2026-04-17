"""The OpenAPI schema stays complete: every view described, no generator warnings."""

from __future__ import annotations

from pathlib import Path

from django.core.management import call_command


def test_openapi_schema_has_no_warnings(tmp_path: Path) -> None:
    out = tmp_path / "schema.yaml"
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(out))
    schema = out.read_text()
    for path in ("/api/v1/reports/cashflow/", "/api/v1/imports/{id}/"):
        assert path in schema
