"""Currency conversion service.

Lookup order:
    1. Django cache (Redis in compose; ``fx:<base>:<quote>:<date>``, TTL 24h).
    2. ``fx_fxrate`` table — persistent history.
    3. Configured provider — fetches and persists, then warms the cache.

A cache outage degrades to DB/provider lookups instead of failing.
``base == quote`` returns ``Decimal('1')`` without I/O.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

from .models import FxRate
from .providers import get_provider

logger = logging.getLogger(__name__)

CACHE_TTL_S = 24 * 3600


def cache_key(base: str, quote: str, on: date) -> str:
    return f"fx:{base}:{quote}:{on.isoformat()}"


def _cache_get(key: str) -> Decimal | None:
    try:
        cached = cache.get(key)
    except Exception as exc:
        logger.warning("fx cache lookup failed: %s", exc)
        return None
    return None if cached is None else Decimal(cached)


def _cache_set(key: str, rate: Decimal) -> None:
    try:
        cache.set(key, str(rate), timeout=CACHE_TTL_S)
    except Exception as exc:
        logger.warning("fx cache set failed: %s", exc)


def get_rate(base: str, quote: str, on: date) -> Decimal | None:
    """Rate such that ``1 base = rate * quote`` on the given day, or ``None``."""
    if base == quote:
        return Decimal("1")

    key = cache_key(base, quote, on)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    row = FxRate.objects.filter(base=base, quote=quote, effective_on=on).first()
    if row is not None:
        _cache_set(key, row.rate)
        return row.rate

    rate = get_provider(settings.FX_PROVIDER).fetch(base, quote, on)
    if rate is None:
        return None
    FxRate.objects.update_or_create(
        base=base, quote=quote, effective_on=on, defaults={"rate": rate}
    )
    _cache_set(key, rate)
    return rate
