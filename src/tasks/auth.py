"""Token blacklist housekeeping."""

from __future__ import annotations

from celery import shared_task
from django.core.management import call_command


@shared_task(name="tasks.auth.flush_expired_tokens")
def flush_expired_tokens() -> None:
    """Drop outstanding and blacklisted refresh tokens that have expired anyway."""
    call_command("flushexpiredtokens")
