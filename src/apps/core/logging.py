"""Minimal JSON log formatter (one object per line, stdlib only)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

# Attributes every LogRecord has; anything else came in via ``extra=``.
_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = {k: v for k, v in vars(record).items() if k not in _RESERVED}
        # django.request attaches the request object; its repr carries the query
        # string (search terms, etc.). Log the path only.
        request = extra.pop("request", None)
        if request is not None:
            extra["path"] = getattr(request, "path", None)
            extra["method"] = getattr(request, "method", None)
        payload.update(extra)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
