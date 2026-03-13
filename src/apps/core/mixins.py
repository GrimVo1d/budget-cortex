"""Reusable queryset-scoping for per-user resources.

All ledger-ish models carry a ``user`` FK and an ``is_deleted`` flag. The
:class:`UserScopedModelViewSet` mixin enforces both: a user can only see
their own non-deleted rows, regardless of any explicit URL parameters.
This guards against IDOR via direct ``pk`` access.
"""

from __future__ import annotations

from typing import Any

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


class UserScopedModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        qs = super().get_queryset()
        # Defensive: every concrete subclass exposes a `.alive()` manager.
        manager = qs.model.objects
        if hasattr(manager, "alive"):
            qs = manager.alive()
        return qs.filter(user_id=self.request.user.id)

    def perform_create(self, serializer: Any) -> None:
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance: Any) -> None:
        from django.utils import timezone

        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
