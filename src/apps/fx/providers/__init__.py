"""Pluggable FX rate provider interface.

Each provider exposes ``fetch(base, quote, on) -> Decimal | None``.
The active provider is chosen via the ``FX_PROVIDER`` setting:

    stub                  — deterministic constants, for tests/local dev
    exchangerate-host     — public free API (TODO, not implemented)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol


class FxProvider(Protocol):
    def fetch(self, base: str, quote: str, on: date) -> Decimal | None: ...


def get_provider(name: str) -> FxProvider:
    if name == "stub":
        from .stub import StubProvider

        return StubProvider()
    raise ValueError(f"unknown FX_PROVIDER: {name!r}")
