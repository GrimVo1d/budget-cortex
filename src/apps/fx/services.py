"""Currency conversion service.

Lookup order:
    1. Redis cache (`fx:<base>:<quote>:<date>`, TTL 24h) — hot reads.
    2. ``fx_rates`` table — persistent history.
    3. Configured provider — fetches and persists, then warms cache.

A successful lookup populates the upper layers so the next call short-circuits.
``base == quote`` returns ``Decimal('1')`` without I/O.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from django.conf import settings

from .models import FxRate
from .providers import get_provider

logger = logging.getLogger(__name__)

_CACHE_TTL_S = 24 * 3600


def _redis_client() -> Any:
    factory = getattr(settings, "FX_REDIS_CLIENT_FACTORY", None)
    if callable(factory):
        return factory()
    import redis  # noqa: PLC0415

    return redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def _cache_key(base: str, quote: str, on: date) -> str:
    return f"fx:{base}:{quote}:{on.isoformat()}"


def get_rate(base: str, quote: str, on: date) -> Decimal | None:
    if base == quote:
        return Decimal("1")

    key = _cache_key(base, quote, on)
    try:
        client = _redis_client()
        cached = client.get(key)
        if cached is not None:
            return Decimal(cached.decode() if isinstance(cached, bytes) else cached)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fx cache lookup failed: %s", exc)
        client = None

    row = (
        FxRate.objects.filter(base=base, quote=quote, effective_on=on)
        .order_by("-effective_on")
        .first()
    )
    if row is not None:
        if client is not None:
            try:
                client.setex(key, _CACHE_TTL_S, str(row.rate))
            except Exception as exc:  # noqa: BLE001
                logger.warning("fx cache set failed: %s", exc)
        return row.rate

    provider = get_provider(settings.FX_PROVIDER)
    rate = provider.fetch(base, quote, on)
    if rate is None:
        return None

    FxRate.objects.update_or_create(
        base=base, quote=quote, effective_on=on, defaults={"rate": rate}
    )
    if client is not None:
        try:
            client.setex(key, _CACHE_TTL_S, str(rate))
        except Exception as exc:  # noqa: BLE001
            logger.warning("fx cache warm failed: %s", exc)
    return rate
