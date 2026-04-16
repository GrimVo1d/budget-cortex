from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime

from django.db import OperationalError
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.auth import user_id
from apps.core.exceptions import ApiError

from .queries.by_category import by_category_report
from .queries.cashflow import cashflow_report
from .queries.overruns import overruns_report
from .serializers import CashflowRowSerializer, CategoryRowSerializer, OverrunRowSerializer

_MONTH_PARAMS = [
    OpenApiParameter("from", str, required=True, description="First month, YYYY-MM"),
    OpenApiParameter("to", str, required=True, description="Month after the last one, YYYY-MM"),
]


_MONTH_RE = re.compile(r"\d{4}-\d{2}")


def _parse_month(name: str, raw: str | None) -> date:
    try:
        if not _MONTH_RE.fullmatch(raw or ""):
            raise ValueError(raw)
        return datetime.strptime(raw or "", "%Y-%m").date()
    except ValueError as exc:
        raise ApiError(f"'{name}' must be YYYY-MM, got {raw!r}", code="invalid_month") from exc


def _month_range(request: Request) -> tuple[date, date]:
    """Parse the half-open ``[from, to)`` month range from query params."""
    from_month = _parse_month("from", request.query_params.get("from"))
    to_month = _parse_month("to", request.query_params.get("to"))
    if to_month <= from_month:
        raise ApiError("'to' must be strictly after 'from'", code="invalid_range")
    return from_month, to_month


# SQLSTATE 55000: a materialized view created WITH NO DATA and never refreshed.
_NOT_POPULATED = "55000"


@contextmanager
def _views_ready() -> Iterator[None]:
    try:
        yield
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) != _NOT_POPULATED:
            raise
        raise ApiError(
            "report data is not built yet; it appears after the next refresh",
            code="report_not_ready",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc


class CashflowReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(parameters=_MONTH_PARAMS, responses=CashflowRowSerializer(many=True))
    def get(self, request: Request) -> Response:
        month_range = _month_range(request)
        with _views_ready():
            rows = cashflow_report(user_id(request), *month_range)
        return Response(CashflowRowSerializer(rows, many=True).data)


class ByCategoryReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(parameters=_MONTH_PARAMS, responses=CategoryRowSerializer(many=True))
    def get(self, request: Request) -> Response:
        month_range = _month_range(request)
        with _views_ready():
            rows = by_category_report(user_id(request), *month_range)
        return Response(CategoryRowSerializer(rows, many=True).data)


class OverrunsReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OverrunRowSerializer(many=True))
    def get(self, request: Request) -> Response:
        with _views_ready():
            rows = overruns_report(user_id(request))
        return Response(OverrunRowSerializer(rows, many=True).data)
