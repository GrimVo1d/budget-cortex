from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from rest_framework.test import APIClient

from tests.factories import make_account, make_category, make_tx

pytestmark = pytest.mark.django_db

BUDGETS = "/api/v1/budgets/"


def _budget(client: APIClient, **extra: Any) -> Any:
    payload = {
        "period": "monthly",
        "period_start": "2026-04-01T00:00:00Z",
        "period_end": "2026-05-01T00:00:00Z",
        "limit_amount": "100.00",
        "currency": "RUB",
        **extra,
    }
    return client.post(BUDGETS, payload, format="json")


def test_status_counts_children_and_matching_currency_only(client: APIClient, user: Any) -> None:
    food = make_category(user, "Food")
    cafe = make_category(user, "Cafe", parent=food)
    salary = make_category(user, "Salary", kind="income")
    rub, usd = make_account(user, "RUB", name="R"), make_account(user, "USD", name="U")
    april = datetime(2026, 4, 10, tzinfo=UTC)
    make_tx(rub, "-60.00", april, food)
    make_tx(rub, "-70.00", april, cafe)
    make_tx(usd, "-999.00", april, food)  # other currency
    make_tx(rub, "500.00", april, salary)  # income
    make_tx(rub, "-1.00", datetime(2026, 5, 1, tzinfo=UTC), food)  # outside period

    budget_id = _budget(client, category=food.pk).json()["id"]
    status = client.get(f"{BUDGETS}{budget_id}/status/").json()

    assert status["spent_amount"] == "130.00"
    assert status["remaining_amount"] == "-30.00"
    assert status["utilization"] == "1.3000"
    assert status["is_over"] is True


def test_overlapping_budgets_are_rejected(client: APIClient, user: Any) -> None:
    food = make_category(user)
    assert _budget(client, category=food.pk).status_code == 201

    overlap = _budget(
        client,
        category=food.pk,
        period_start="2026-04-15T00:00:00Z",
        period_end="2026-05-15T00:00:00Z",
    )
    assert overlap.status_code == 400

    adjacent = _budget(
        client,
        category=food.pk,
        period_start="2026-05-01T00:00:00Z",
        period_end="2026-06-01T00:00:00Z",
    )
    assert adjacent.status_code == 201

    other_currency = _budget(client, category=food.pk, currency="USD")
    assert other_currency.status_code == 201


def test_period_end_must_follow_start(client: APIClient) -> None:
    resp = _budget(client, period_end="2026-04-01T00:00:00Z")
    assert resp.status_code == 400


def test_utilization_of_a_zero_limit_is_null(client: APIClient, user: Any) -> None:
    food = make_category(user, "Food")
    make_tx(make_account(user), "-5.00", datetime(2026, 4, 2, tzinfo=UTC), food)
    budget_id = _budget(client, category=food.pk, limit_amount="0.00").json()["id"]

    status = client.get(f"{BUDGETS}{budget_id}/status/").json()

    assert status["utilization"] is None
    assert status["is_over"] is True


def test_status_handles_a_huge_ratio_to_a_tiny_limit(client: APIClient, user: Any) -> None:
    food = make_category(user, "Food")
    acc = make_account(user)
    for day in (2, 3):
        make_tx(acc, "-999999999999.99", datetime(2026, 4, day, tzinfo=UTC), food)
    budget_id = _budget(client, category=food.pk, limit_amount="0.01").json()["id"]

    resp = client.get(f"{BUDGETS}{budget_id}/status/")

    assert resp.status_code == 200
    assert resp.json()["spent_amount"] == "1999999999999.98"
    assert resp.json()["utilization"] == "199999999999998.0000"
