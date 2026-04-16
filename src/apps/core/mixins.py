"""Per-user scoping for viewsets.

All ledger-ish models carry a ``user`` FK and an ``is_deleted`` flag.
:class:`UserScopedModelViewSet` enforces both: a user only ever sees their
own live rows, so another user's ids simply 404 (no IDOR, no existence
oracle). ``DELETE`` is a soft delete.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .audit import AuditActorMixin


class UserScopedModelViewSet(AuditActorMixin, viewsets.ModelViewSet):  # type: ignore[type-arg]
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> models.QuerySet[Any]:
        qs: models.QuerySet[Any] = super().get_queryset()
        return qs.filter(user_id=self.request.user.pk, is_deleted=False)

    def perform_create(self, serializer: Any) -> None:
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance: Any) -> None:
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
