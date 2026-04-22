"""CSV parsers, without Celery or the database."""

from __future__ import annotations

import io

import pytest

from apps.imports.parsers import (
    ImportFormatError,
    disambiguate,
    parse_generic,
    parse_sberbank,
    parse_tinkoff,
)


def _lines(s: str) -> io.StringIO:
    return io.StringIO(s)


def test_generic_parses_iso_date_and_decimal() -> None:
    rows = list(
        parse_generic(
            _lines("date,amount,currency,description\n2026-04-01T12:00:00,-100.50,usd,Coffee\n")
        )
    )
    assert len(rows) == 1
    assert str(rows[0].amount) == "-100.50"
    assert rows[0].currency == "USD"
    assert rows[0].description == "Coffee"
    assert rows[0].occurred_at.tzinfo is not None


def test_generic_columns_can_be_reordered_and_optional() -> None:
    rows = list(parse_generic(_lines("Amount,Date\n250,2026-04-01\n")))
    assert rows[0].currency is None  # filled from the account by the import task
    assert rows[0].description == ""


@pytest.mark.parametrize(
    "src",
    [
        "date,amount\nnope,1\n",
        "date,amount\n2026-04-01,NaN\n",
        "date,amount,currency\n2026-04-01,1,RUBX\n",
        "date,amount,currency\n2026-04-01,1,\u0440\u0443\u0431\n",  # Cyrillic
        "date,amount,currency\n2026-04-01,1\n",
        "when,how_much\n2026-04-01,1\n",
    ],
)
def test_generic_rejects_bad_input(src: str) -> None:
    with pytest.raises(ImportFormatError):
        list(parse_generic(_lines(src)))


def test_tinkoff_parses_ru_format() -> None:
    rows = list(
        parse_tinkoff(
            _lines("Date;Amount;Currency;Description\n01.04.2026 12:00:00;-1 000,50;RUB;Coffee\n")
        )
    )
    assert str(rows[0].amount) == "-1000.50"


def test_tinkoff_short_row_raises() -> None:
    with pytest.raises(ImportFormatError):
        list(parse_tinkoff(_lines("Date;Amount\n01.04.2026 12:00:00;-100\n")))


def test_sberbank_parses_date_only() -> None:
    rows = list(parse_sberbank(_lines("Date,Amount,Description\n01.04.2026,500,Salary\n")))
    assert rows[0].currency == "RUB"
    assert str(rows[0].amount) == "500"


def test_hash_is_stable_and_repeats_are_disambiguated() -> None:
    src = "date,amount\n2026-04-01T12:00:00,-3\n2026-04-01T12:00:00,-3\n"
    first = [r.raw_hash for r in disambiguate(parse_generic(_lines(src)))]
    second = [r.raw_hash for r in disambiguate(parse_generic(_lines(src)))]
    assert first == second
    assert len(set(first)) == 2
