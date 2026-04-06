"""CSV parsers for bank statements.

Each parser yields :class:`ParsedRow` regardless of source format so the
downstream task can stay format-agnostic. New banks are added by writing
another ``parse_*`` function and registering it in :data:`PARSERS`.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation


class ImportFormatError(ValueError):
    """Raised when a CSV row cannot be parsed for the declared format."""


@dataclass(frozen=True)
class ParsedRow:
    occurred_at: datetime
    amount: Decimal  # signed: negative for outflow
    currency: str
    description: str
    raw_hash: str  # sha256 of the original line; used for dedup


def _hash_line(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _to_decimal(raw: str) -> Decimal:
    cleaned = raw.replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ImportFormatError(f"bad amount {raw!r}") from exc


def parse_generic(stream: Iterable[str]) -> Iterator[ParsedRow]:
    """Header: ``date,amount,currency,description``. Dates ISO-8601."""
    reader = csv.DictReader(stream)
    for row in reader:
        try:
            occurred_at = datetime.fromisoformat(row["date"]).replace(tzinfo=UTC)
            yield ParsedRow(
                occurred_at=occurred_at,
                amount=_to_decimal(row["amount"]),
                currency=row.get("currency", "RUB").strip().upper(),
                description=row.get("description", "").strip(),
                raw_hash=_hash_line(",".join(row.values())),
            )
        except (KeyError, ValueError) as exc:
            raise ImportFormatError(str(exc)) from exc


def parse_tinkoff(stream: Iterable[str]) -> Iterator[ParsedRow]:
    """Tinkoff RU export: ``DD.MM.YYYY HH:MM:SS;amount;currency;description``."""
    reader = csv.reader(stream, delimiter=";")
    header = next(reader, None)
    if header is None:
        return
    for row in reader:
        if len(row) < 4:
            raise ImportFormatError(f"short row {row!r}")
        try:
            occurred_at = datetime.strptime(row[0], "%d.%m.%Y %H:%M:%S").replace(tzinfo=UTC)
        except ValueError as exc:
            raise ImportFormatError(f"bad date {row[0]!r}") from exc
        yield ParsedRow(
            occurred_at=occurred_at,
            amount=_to_decimal(row[1]),
            currency=row[2].strip().upper() or "RUB",
            description=row[3].strip(),
            raw_hash=_hash_line(";".join(row)),
        )


def parse_sberbank(stream: Iterable[str]) -> Iterator[ParsedRow]:
    """Sberbank export: ``DD.MM.YYYY,amount,description`` (currency=RUB)."""
    reader = csv.reader(stream)
    header = next(reader, None)
    if header is None:
        return
    for row in reader:
        if len(row) < 3:
            raise ImportFormatError(f"short row {row!r}")
        try:
            occurred_at = datetime.strptime(row[0], "%d.%m.%Y").replace(tzinfo=UTC)
        except ValueError as exc:
            raise ImportFormatError(f"bad date {row[0]!r}") from exc
        yield ParsedRow(
            occurred_at=occurred_at,
            amount=_to_decimal(row[1]),
            currency="RUB",
            description=row[2].strip(),
            raw_hash=_hash_line(",".join(row)),
        )


PARSERS = {
    "generic": parse_generic,
    "tinkoff": parse_tinkoff,
    "sberbank": parse_sberbank,
}


def parse_file(path: str, fmt: str) -> Iterator[ParsedRow]:
    parser = PARSERS.get(fmt)
    if parser is None:
        raise ImportFormatError(f"unknown format {fmt!r}")
    # utf-8-sig strips a BOM if the bank tool wrote one.
    with open(path, encoding="utf-8-sig", newline="") as fh:
        stream = io.StringIO(fh.read())
    yield from parser(stream)
