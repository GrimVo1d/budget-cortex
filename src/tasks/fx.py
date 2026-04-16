"""Daily FX rate fetch."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Account
from apps.fx.services import get_rate
from apps.ledger.models import Transaction

logger = logging.getLogger(__name__)


@shared_task(
    name="tasks.fx.fetch_fx_rates",
    autoretry_for=(OSError,),
    retry_backoff=60,
    max_retries=3,
)
def fetch_fx_rates() -> dict[str, str | None]:
    """Store today's rate to ``FX_BASE_CURRENCY`` for every currency in use."""
    base = settings.FX_BASE_CURRENCY
    today = timezone.now().date()
    currencies = set(
        Account.objects.filter(is_deleted=False).values_list("currency", flat=True).distinct()
    ) | set(
        Transaction.objects.filter(is_deleted=False).values_list("currency", flat=True).distinct()
    )
    currencies.discard(base)

    results: dict[str, str | None] = {}
    for currency in sorted(currencies):
        rate = get_rate(currency, base, today)
        results[f"{currency}/{base}"] = None if rate is None else str(rate)
        if rate is None:
            logger.warning("fx_rate_unavailable", extra={"base": currency, "quote": base})
    return results
