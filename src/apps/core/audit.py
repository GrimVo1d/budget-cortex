"""Application-side audit log.

Captures create/update/delete events for ``Account``, ``Transaction``, and
``Budget``. The actor is sourced from a thread-local set by
:class:`AuditMiddleware` so signal handlers can attribute writes without
plumbing a user kwarg through every service.

This is intentionally NOT a triggers-on-the-database solution — keeping the
recorder in Python lets us include serializer-level intent (`reason`) and
swap the storage backend (e.g. write-once to S3) later without DDL.
"""

from __future__ import annotations

import threading
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.forms.models import model_to_dict

_local = threading.local()


def set_actor(user_id: int | None) -> None:
    _local.actor_id = user_id


def get_actor() -> int | None:
    return getattr(_local, "actor_id", None)


def clear_actor() -> None:
    _local.actor_id = None


class AuditAction(models.TextChoices):
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    model = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    action = models.CharField(max_length=16, choices=AuditAction.choices)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["model", "object_id"], name="audit_model_obj_idx"),
            models.Index(fields=["actor", "-at"], name="audit_actor_at_idx"),
        ]
        ordering = ["-at"]


def _serialise(instance: Any) -> dict[str, Any]:
    raw = model_to_dict(instance)
    # JSONField requires JSON-able primitives; cast Decimal/datetime via str.
    return {
        k: str(v) if v is not None and not isinstance(v, (int, bool, str)) else v
        for k, v in raw.items()
    }


_AUDITED_MODELS = {"Account", "Transaction", "Budget"}


@receiver(post_save)
def _record_save(sender, instance, created, **kwargs):
    if sender.__name__ not in _AUDITED_MODELS:
        return
    AuditLog.objects.create(
        actor_id=get_actor(),
        model=sender.__name__,
        object_id=str(instance.pk),
        action=AuditAction.CREATE if created else AuditAction.UPDATE,
        before={},  # before-state requires fetching pre-save row; left empty for v1
        after=_serialise(instance),
    )


@receiver(post_delete)
def _record_delete(sender, instance, **kwargs):
    if sender.__name__ not in _AUDITED_MODELS:
        return
    AuditLog.objects.create(
        actor_id=get_actor(),
        model=sender.__name__,
        object_id=str(instance.pk),
        action=AuditAction.DELETE,
        before=_serialise(instance),
        after={},
    )
