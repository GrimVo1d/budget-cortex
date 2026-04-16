"""Ordering with a deterministic tie-breaker."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.views import APIView


class StableOrderingFilter(OrderingFilter):
    """Append ``id`` (in the direction of the last key) to any ordering.

    Without it rows with equal keys (same ``occurred_at``) come back in
    arbitrary order, which also makes the running balance look shuffled.
    """

    def get_ordering(
        self, request: Request, queryset: QuerySet[Any], view: APIView
    ) -> list[str] | None:
        requested = super().get_ordering(request, queryset, view)
        if not requested:
            return None
        ordering = list(requested)
        if not any(f.lstrip("-") in ("id", "pk") for f in ordering):
            ordering.append("-id" if ordering[-1].startswith("-") else "id")
        return ordering
