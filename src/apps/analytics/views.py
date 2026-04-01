from __future__ import annotations

from datetime import UTC, date, datetime

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .queries.cashflow import cashflow_report


def _parse_month(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m").replace(tzinfo=UTC).date().replace(day=1)
    except ValueError as exc:
        raise serializers.ValidationError(
            {"detail": f"month must be YYYY-MM, got {raw!r}"}
        ) from exc


class CashflowReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from_month = _parse_month(request.query_params.get("from", ""))
        to_month = _parse_month(request.query_params.get("to", ""))
        if to_month <= from_month:
            return Response(
                {"code": "invalid_range", "detail": "'to' must be strictly after 'from'"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = cashflow_report(request.user.id, from_month, to_month)
        return Response(
            [
                {
                    "month": r.month.isoformat(),
                    "currency": r.currency,
                    "income": str(r.income),
                    "expense": str(r.expense),
                    "net": str(r.net),
                }
                for r in rows
            ]
        )
