from __future__ import annotations

from decimal import Decimal

import pytest

from apps.core.csv import sanitize_cell


@pytest.mark.parametrize(
    "value", ["=1+1", "+7", "-cmd", "@SUM(A1)", "\tx", "\rx", " =1+1", "\n=1+1"]
)
def test_formula_like_text_is_prefixed(value: str) -> None:
    assert sanitize_cell(value) == "'" + value


@pytest.mark.parametrize("value", ["Coffee", "", 5, Decimal("-1.00"), None])
def test_other_values_pass_through(value: object) -> None:
    assert sanitize_cell(value) == value
