"""Serializer and filter fields restricted to the requesting user's rows.

Using these instead of ``queryset=Model.objects.all()`` means another
user's id and a non-existent id produce the same "does not exist" error,
and soft-deleted rows cannot be referenced.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.http import HttpRequest
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


def owned(model: type[models.Model], request: HttpRequest | None) -> models.QuerySet[Any]:
    """Live rows of ``model`` owned by ``request.user`` (none without a request)."""
    manager: models.Manager[Any] = model._default_manager
    if request is None or not request.user.is_authenticated:
        return manager.none()
    return manager.filter(user_id=request.user.pk, is_deleted=False)


# All models here use integer primary keys; spectacular cannot infer that for
# fields on plain (model-less) serializers.
@extend_schema_field(OpenApiTypes.INT)
class OwnedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):  # type: ignore[type-arg]
    def __init__(self, model: type[models.Model], **kwargs: Any) -> None:
        self.owned_model = model
        super().__init__(**kwargs)

    def get_queryset(self) -> models.QuerySet[Any]:
        return owned(self.owned_model, self.context.get("request"))

    def to_internal_value(self, data: Any) -> Any:
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError:
            # Re-sending the value the object already has is fine even if that
            # row was deleted since (e.g. a transaction's archived category).
            current = self._current_value()
            if current is not None and str(current.pk) == str(data):
                return current
            raise

    def _current_value(self) -> models.Model | None:
        instance = getattr(self.parent, "instance", None)
        if not isinstance(instance, models.Model) or not self.source:
            return None
        value = getattr(instance, self.source, None)
        return value if isinstance(value, models.Model) else None

    def use_pk_only_optimization(self) -> bool:
        return True
