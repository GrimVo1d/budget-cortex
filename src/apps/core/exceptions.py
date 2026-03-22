"""Centralised DRF exception → response shape.

All 4xx replies follow ``{"code": "<machine_readable>", "detail": "<human>"}``.
This lets API consumers branch on the stable ``code`` while ``detail`` is
free to evolve.
"""

from __future__ import annotations

from typing import Any

from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

_EXCEPTION_CODES: dict[type[Exception], str] = {
    exceptions.AuthenticationFailed: "authentication_failed",
    exceptions.NotAuthenticated: "not_authenticated",
    exceptions.PermissionDenied: "permission_denied",
    exceptions.NotFound: "not_found",
    exceptions.MethodNotAllowed: "method_not_allowed",
    exceptions.Throttled: "throttled",
    exceptions.ParseError: "parse_error",
    exceptions.UnsupportedMediaType: "unsupported_media_type",
    exceptions.ValidationError: "validation_error",
}


def code_for(exc: Exception) -> str:
    for cls, code in _EXCEPTION_CODES.items():
        if isinstance(exc, cls):
            return code
    return "error"


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = drf_default_handler(exc, context)
    if response is None:
        return None

    code = code_for(exc)
    detail = response.data
    response.data = {"code": code, "detail": detail}
    return response
