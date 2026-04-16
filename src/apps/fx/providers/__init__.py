"""Pluggable FX rate provider interface.

Each provider exposes ``fetch(base, quote, on) -> Decimal | None``.
The active provider is chosen via the ``FX_PROVIDER`` setting. Only
``stub`` (deterministic constants) ships with the project; a real provider
is one more class here plus a branch in :func:`get_provider`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from .stub import StubProvider


class FxProvider(Protocol):
    def fetch(self, base: str, quote: str, on: date) -> Decimal | None: ...


def get_provider(name: str) -> FxProvider:
    if name == "stub":
        return StubProvider()
    raise ValueError(f"unknown FX_PROVIDER: {name!r}")
