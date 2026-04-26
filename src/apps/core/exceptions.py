"""Centralised DRF exception → response shape.

Every error reply is ``{"code": "<machine_readable>", "detail": <human>}``.
Clients branch on the stable ``code``; ``detail`` is free to evolve.
"""

from __future__ import annotations

import logging
from decimal import InvalidOperation
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import DataError, IntegrityError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

logger = logging.getLogger(__name__)


class ApiError(exceptions.APIException):
    """An error with an explicit machine-readable code and HTTP status."""

    def __init__(self, detail: str, code: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(detail=detail, code=code)
        self.status_code = status_code
        self.error_code = code


def code_for(exc: Exception) -> str:
    if isinstance(exc, ApiError):
        return exc.error_code
    if isinstance(exc, exceptions.ValidationError):
        return "validation_error"
    if isinstance(exc, Http404):
        return "not_found"
    if isinstance(exc, DjangoPermissionDenied):
        return "permission_denied"
    if isinstance(exc, exceptions.APIException):
        return str(exc.default_code)
    return "error"


# Keys of an error body that already is ``{"detail": ...}``-shaped (DRF's own,
# or simplejwt's ``{"detail", "code", "messages"}``); it is unwrapped.
_WRAPPED_KEYS = {"detail", "code", "messages"}


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, IntegrityError):
        # Serializers validate uniqueness; this is the race that slipped past them.
        return Response(
            {"code": "conflict", "detail": "conflicts with an existing record"},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, DataError | InvalidOperation):
        # A 400 for the client, but a traceback for us: this can also be a server bug.
        logger.warning("value_out_of_range", exc_info=exc)
        # e.g. a computed amount that does not fit NUMERIC(14, 2), or a Decimal
        # operation out of the context's range.
        return Response(
            {"code": "invalid_value", "detail": "a value is out of range"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    response = drf_default_handler(exc, context)
    if response is None:
        return None
    detail = response.data
    if isinstance(detail, dict) and "detail" in detail and set(detail) <= _WRAPPED_KEYS:
        detail = detail["detail"]
    response.data = {"code": code_for(exc), "detail": detail}
    return response
