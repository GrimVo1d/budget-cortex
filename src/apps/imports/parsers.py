"""CSV parsers for bank statements.

Each parser yields :class:`ParsedRow` regardless of source format so the
downstream task can stay format-agnostic. New banks are added by writing
another ``parse_*`` function and registering it in :data:`PARSERS`.

``raw_hash`` identifies a statement line for idempotent re-imports. Two
genuinely identical lines in one file (same date, amount and text) are kept
apart by an occurrence counter, see :func:`parse_file`.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


class ImportFormatError(ValueError):
    """Raised when a CSV row cannot be parsed for the declared format."""


@dataclass(frozen=True)
class ParsedRow:
    occurred_at: datetime
    amount: Decimal  # signed: negative for outflow
    currency: str | None  # None: not in the file, the import uses the account's currency
    description: str
    raw_hash: str  # sha256 of the source cells; used for dedup


def _hash_cells(cells: Iterable[str]) -> str:
    return hashlib.sha256("\x1f".join(cells).encode("utf-8")).hexdigest()


def _to_decimal(raw: str) -> Decimal:
    cleaned = raw.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ImportFormatError(f"bad amount {raw!r}") from exc
    if not value.is_finite():
        raise ImportFormatError(f"bad amount {raw!r}")
    return value


_CURRENCY_RE = re.compile(r"[A-Z]{3}")


def _to_currency(raw: str) -> str | None:
    code = raw.strip().upper()
    if not code:
        return None
    if not _CURRENCY_RE.fullmatch(code):
        raise ImportFormatError(f"bad currency {raw!r}")
    return code


def _to_datetime(raw: str, fmt: str | None) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw) if fmt is None else datetime.strptime(raw, fmt)
    except ValueError as exc:
        raise ImportFormatError(f"bad date {raw!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_generic(stream: Iterable[str]) -> Iterator[ParsedRow]:
    """Header with ``date,amount`` and optional ``currency,description``. ISO-8601 dates."""
    reader = csv.reader(stream)
    header = [h.strip().lower() for h in next(reader, [])]
    try:
        i_date, i_amount = header.index("date"), header.index("amount")
    except ValueError as exc:
        raise ImportFormatError("header must contain 'date' and 'amount'") from exc
    i_cur = header.index("currency") if "currency" in header else None
    i_desc = header.index("description") if "description" in header else None

    for row in reader:
        if not row:
            continue
        if len(row) < len(header):
            raise ImportFormatError(f"short row on line {reader.line_num}")
        yield ParsedRow(
            occurred_at=_to_datetime(row[i_date], None),
            amount=_to_decimal(row[i_amount]),
            currency=_to_currency(row[i_cur] if i_cur is not None else ""),
            description=row[i_desc].strip() if i_desc is not None else "",
            raw_hash=_hash_cells(row),
        )


def parse_tinkoff(stream: Iterable[str]) -> Iterator[ParsedRow]:
    """Tinkoff export: ``DD.MM.YYYY HH:MM:SS;amount;currency;description``."""
    reader = csv.reader(stream, delimiter=";")
    next(reader, None)  # header
    for row in reader:
        if not row:
            continue
        if len(row) < 4:
            raise ImportFormatError(f"short row on line {reader.line_num}")
        yield ParsedRow(
            occurred_at=_to_datetime(row[0], "%d.%m.%Y %H:%M:%S"),
            amount=_to_decimal(row[1]),
            currency=_to_currency(row[2]),
            description=row[3].strip(),
            raw_hash=_hash_cells(row),
        )


def parse_sberbank(stream: Iterable[str]) -> Iterator[ParsedRow]:
    """Sberbank export: ``DD.MM.YYYY,amount,description`` (currency is always RUB)."""
    reader = csv.reader(stream)
    next(reader, None)  # header
    for row in reader:
        if not row:
            continue
        if len(row) < 3:
            raise ImportFormatError(f"short row on line {reader.line_num}")
        yield ParsedRow(
            occurred_at=_to_datetime(row[0], "%d.%m.%Y"),
            amount=_to_decimal(row[1]),
            currency="RUB",
            description=row[2].strip(),
            raw_hash=_hash_cells(row),
        )


PARSERS: dict[str, Callable[[Iterable[str]], Iterator[ParsedRow]]] = {
    "generic": parse_generic,
    "tinkoff": parse_tinkoff,
    "sberbank": parse_sberbank,
}


def disambiguate(rows: Iterable[ParsedRow]) -> Iterator[ParsedRow]:
    """Give the n-th repeat of an identical line its own hash (n >= 1).

    The first occurrence keeps the plain hash, so re-importing the same or
    an overlapping statement still deduplicates line by line.
    """
    seen: Counter[str] = Counter()
    for row in rows:
        n = seen[row.raw_hash]
        seen[row.raw_hash] += 1
        yield row if n == 0 else replace(row, raw_hash=_hash_cells([row.raw_hash, str(n)]))


def parse_file(path: Path, fmt: str) -> Iterator[ParsedRow]:
    parser = PARSERS.get(fmt)
    if parser is None:
        raise ImportFormatError(f"unknown format {fmt!r}")
    # utf-8-sig strips a BOM if the bank tool wrote one.
    with path.open(encoding="utf-8-sig", newline="") as fh:
        try:
            yield from disambiguate(parser(fh))
        except UnicodeDecodeError as exc:
            raise ImportFormatError("file is not valid UTF-8") from exc
        except csv.Error as exc:
            raise ImportFormatError(f"malformed CSV: {exc}") from exc
