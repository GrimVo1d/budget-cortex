"""Liveness / readiness probes (unauthenticated, unthrottled)."""

from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class LivenessView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(exclude=True)
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadinessView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(exclude=True)
    def get(self, request: Request) -> Response:
        checks: dict[str, str] = {}
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"
        try:
            cache.set("health:ready", "1", timeout=5)
            checks["cache"] = "ok" if cache.get("health:ready") == "1" else "error"
        except Exception:
            checks["cache"] = "error"
        ok = all(v == "ok" for v in checks.values())
        return Response({"status": "ok" if ok else "error", **checks}, status=200 if ok else 503)
