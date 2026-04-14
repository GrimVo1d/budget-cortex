"""Unit tests for CSV parsers.

Exercises the three supported formats without going through Celery or the DB.
"""

from __future__ import annotations

import io

import pytest

from apps.imports.parsers import (
    ImportFormatError,
    parse_generic,
    parse_sberbank,
    parse_tinkoff,
)


def _lines(s: str) -> list[str]:
    return io.StringIO(s).readlines()


def test_generic_parses_iso_date_and_decimal():
    rows = list(
        parse_generic(
            _lines("date,amount,currency,description\n" "2026-04-01T12:00:00,-100.50,RUB,Coffee\n")
        )
    )
    assert len(rows) == 1
    assert str(rows[0].amount) == "-100.50"
    assert rows[0].currency == "RUB"
    assert rows[0].description == "Coffee"


def test_generic_strips_utf8_bom_via_dictreader_header():
    rows = list(
        parse_generic(
            _lines("date,amount,currency,description\n" "2026-04-01T12:00:00,250,USD,Refund\n")
        )
    )
    assert rows[0].currency == "USD"


def test_generic_bad_date_raises():
    with pytest.raises(ImportFormatError):
        list(parse_generic(_lines("date,amount,currency,description\nnope,1,RUB,x\n")))


def test_tinkoff_parses_ru_format():
    rows = list(
        parse_tinkoff(
            _lines("Date;Amount;Currency;Description\n" "01.04.2026 12:00:00;-100,50;RUB;Coffee\n")
        )
    )
    assert str(rows[0].amount) == "-100.50"
    assert rows[0].currency == "RUB"


def test_tinkoff_short_row_raises():
    with pytest.raises(ImportFormatError):
        list(parse_tinkoff(_lines("Date;Amount\n01.04.2026 12:00:00;-100\n")))


def test_sberbank_parses_date_only():
    rows = list(parse_sberbank(_lines("Date,Amount,Description\n01.04.2026,500,Salary\n")))
    assert rows[0].currency == "RUB"
    assert str(rows[0].amount) == "500"


def test_raw_hash_is_stable_per_row():
    src = "date,amount,currency,description\n2026-04-01T12:00:00,-100,RUB,x\n"
    a = list(parse_generic(_lines(src)))
    b = list(parse_generic(_lines(src)))
    assert a[0].raw_hash == b[0].raw_hash
