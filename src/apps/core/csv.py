"""Streaming CSV responses with spreadsheet formula-injection protection."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from typing import Any

from django.http import StreamingHttpResponse

# A text cell starting with one of these is evaluated as a formula by
# Excel / LibreOffice. Prefixing a quote keeps it plain text.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value: Any) -> Any:
    # Leading whitespace is checked too: some spreadsheets trim it on import.
    if isinstance(value, str) and (
        value.startswith(_FORMULA_PREFIXES) or value.lstrip().startswith(_FORMULA_PREFIXES)
    ):
        return "'" + value
    return value


class _Echo:
    """File-like object whose ``write`` returns the value (for csv.writer)."""

    def write(self, value: str) -> str:
        return value


def stream_csv(rows: Iterable[Iterable[Any]], filename: str) -> StreamingHttpResponse:
    """Stream ``rows`` as a CSV attachment.

    Only ``str`` cells are sanitized; pass numbers as numbers (e.g.
    ``Decimal``) so a negative amount is not mangled.
    """
    writer = csv.writer(_Echo())

    def _iter() -> Iterator[str]:
        for row in rows:
            yield writer.writerow([sanitize_cell(v) for v in row])

    response = StreamingHttpResponse(_iter(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
