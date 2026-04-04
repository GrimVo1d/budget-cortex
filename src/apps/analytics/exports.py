"""Streaming CSV exports for reports and transactions."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from typing import Any

from django.http import StreamingHttpResponse


class _Echo:
    """File-like object whose ``write`` returns the value (for csv.writer)."""

    def write(self, value: str) -> str:
        return value


def stream_csv(rows: Iterable[Iterable[Any]], filename: str) -> StreamingHttpResponse:
    writer = csv.writer(_Echo())

    def _iter() -> Iterator[str]:
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(_iter(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
