"""Application-side audit log recorder.

Every save/delete of an audited model writes an :class:`AuditLog` row with
before/after snapshots. A soft delete (``is_deleted`` flipping to true) is
recorded as ``delete``.

The actor lives in a :class:`~contextvars.ContextVar` so it is safe under
threads and async alike. :class:`AuditMiddleware` sets it for session-based
requests (admin); DRF views set it after their own authentication via
:class:`AuditActorMixin`, because JWT is only resolved inside the view.
"""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from rest_framework.request import Request

from .models import AuditAction, AuditLog

AUDITED_MODELS = frozenset(
    {"accounts.Account", "ledger.Category", "ledger.Transaction", "budgets.Budget"}
)

_actor: ContextVar[int | None] = ContextVar("audit_actor", default=None)


def set_actor(user_id: int | None) -> Token[int | None]:
    return _actor.set(user_id)


def reset_actor(token: Token[int | None]) -> None:
    _actor.reset(token)


def get_actor() -> int | None:
    return _actor.get()


class AuditActorMixin:
    """Bind the DRF-authenticated user as the audit actor for this request."""

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)  # type: ignore[misc]
        if request.user.is_authenticated:
            set_actor(request.user.pk)


def _is_audited(sender: type[models.Model]) -> bool:
    return sender._meta.label in AUDITED_MODELS


def snapshot(instance: models.Model) -> dict[str, Any]:
    """JSON-safe dict of the instance's concrete column values."""
    raw = {f.attname: getattr(instance, f.attname) for f in instance._meta.concrete_fields}
    result: dict[str, Any] = json.loads(json.dumps(raw, cls=DjangoJSONEncoder))
    return result


def _record(
    instance: models.Model, action: str, before: dict[str, Any], after: dict[str, Any]
) -> None:
    AuditLog.objects.create(
        actor_id=get_actor(),
        model=instance._meta.label,
        object_id=str(instance.pk),
        action=action,
        before=before,
        after=after,
    )


@receiver(pre_save)
def _capture_before(sender: type[models.Model], instance: models.Model, **kwargs: Any) -> None:
    if not _is_audited(sender) or instance.pk is None:
        return
    previous = sender._base_manager.filter(pk=instance.pk).first()
    instance._audit_before = snapshot(previous) if previous is not None else {}  # type: ignore[attr-defined]


@receiver(post_save)
def _record_save(
    sender: type[models.Model], instance: models.Model, created: bool, **kwargs: Any
) -> None:
    if not _is_audited(sender):
        return
    before: dict[str, Any] = getattr(instance, "_audit_before", {})
    after = snapshot(instance)
    if created:
        action = AuditAction.CREATE
    elif after.get("is_deleted") and not before.get("is_deleted", False):
        action = AuditAction.DELETE
    else:
        action = AuditAction.UPDATE
    _record(instance, action, before, after)


@receiver(post_delete)
def _record_delete(sender: type[models.Model], instance: models.Model, **kwargs: Any) -> None:
    if _is_audited(sender):
        _record(instance, AuditAction.DELETE, snapshot(instance), {})
