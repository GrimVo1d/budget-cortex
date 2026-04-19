from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from django.http import StreamingHttpResponse
from rest_framework.test import APIClient

from apps.ledger.models import Transaction, TransactionType
from tests.factories import make_account, make_category, make_tx

pytestmark = pytest.mark.django_db

TX = "/api/v1/transactions/"
TRANSFER = "/api/v1/transactions/transfer/"


def test_list_includes_running_balance_with_opening(client: APIClient, user: Any) -> None:
    acc = make_account(user, opening="100.00")
    make_tx(acc, "-30.00", datetime(2026, 4, 1, tzinfo=UTC))
    make_tx(acc, "50.00", datetime(2026, 4, 2, tzinfo=UTC))

    rows = client.get(TX, {"ordering": "occurred_at"}).json()["results"]

    assert [r["running_balance"] for r in rows] == ["70.00", "120.00"]


def test_running_balance_ignores_page_and_filter_boundaries(client: APIClient, user: Any) -> None:
    acc = make_account(user)
    make_tx(acc, "10.00", datetime(2026, 3, 1, tzinfo=UTC))
    make_tx(acc, "5.00", datetime(2026, 4, 1, tzinfo=UTC))

    rows = client.get(TX, {"occurred_from": "2026-03-15T00:00:00Z"}).json()["results"]

    assert [r["running_balance"] for r in rows] == ["15.00"]


def test_transfer_creates_linked_legs(client: APIClient, user: Any) -> None:
    a, b = make_account(user, name="A"), make_account(user, name="B")
    resp = client.post(
        TRANSFER,
        {
            "from_account": a.pk,
            "to_account": b.pk,
            "amount": "25.00",
            "occurred_at": "2026-04-01T10:00:00Z",
        },
        format="json",
    )
    assert resp.status_code == 201
    debit, credit = resp.json()["debit"], resp.json()["credit"]
    assert (debit["amount"], credit["amount"]) == ("-25.00", "25.00")
    assert debit["transfer_pair"] == credit["id"]
    assert credit["transfer_pair"] == debit["id"]
    assert debit["type"] == "transfer"


def test_cross_currency_transfer_requires_positive_rate(client: APIClient, user: Any) -> None:
    rub, usd = make_account(user, "RUB", name="R"), make_account(user, "USD", name="U")
    base = {
        "from_account": usd.pk,
        "to_account": rub.pk,
        "amount": "10.00",
        "occurred_at": "2026-04-01T10:00:00Z",
    }

    missing = client.post(TRANSFER, base, format="json")
    assert missing.status_code == 400
    assert missing.json()["code"] == "transfer_error"

    negative = client.post(TRANSFER, {**base, "fx_rate": "-5"}, format="json")
    assert negative.status_code == 400

    ok = client.post(TRANSFER, {**base, "fx_rate": "92.5"}, format="json")
    assert ok.status_code == 201
    assert ok.json()["credit"]["amount"] == "925.00"


def test_transfer_to_foreign_account_is_rejected(
    client: APIClient, user: Any, other_user: Any
) -> None:
    mine, theirs = make_account(user), make_account(other_user)
    resp = client.post(
        TRANSFER,
        {
            "from_account": mine.pk,
            "to_account": theirs.pk,
            "amount": "1.00",
            "occurred_at": "2026-04-01T10:00:00Z",
        },
        format="json",
    )
    assert resp.status_code == 400
    assert not Transaction.objects.exists()


def test_transfer_legs_are_immutable_and_deleted_together(client: APIClient, user: Any) -> None:
    a, b = make_account(user, name="A"), make_account(user, name="B")
    legs = client.post(
        TRANSFER,
        {
            "from_account": a.pk,
            "to_account": b.pk,
            "amount": "5.00",
            "occurred_at": "2026-04-01T10:00:00Z",
        },
        format="json",
    ).json()
    debit_id = legs["debit"]["id"]

    assert client.patch(f"{TX}{debit_id}/", {"amount": "-1.00"}, format="json").status_code == 400
    assert client.delete(f"{TX}{debit_id}/").status_code == 204
    assert Transaction.objects.filter(is_deleted=False).count() == 0


def test_transfer_type_cannot_be_set_directly(client: APIClient, account: Any) -> None:
    resp = client.post(
        TX,
        {
            "account": account.pk,
            "amount": "1.00",
            "currency": "RUB",
            "occurred_at": "2026-04-01T12:00:00Z",
            "type": TransactionType.TRANSFER,
        },
        format="json",
    )
    assert resp.status_code == 400


def test_category_with_children_cannot_become_child(client: APIClient, user: Any) -> None:
    root, other_root = make_category(user, "Food"), make_category(user, "Fun")
    make_category(user, "Cafe", parent=root)

    resp = client.patch(f"/api/v1/categories/{root.pk}/", {"parent": other_root.pk}, format="json")

    assert resp.status_code == 400


def test_export_neutralises_formulas_but_keeps_negative_amounts(
    client: APIClient, account: Any
) -> None:
    tx = make_tx(account, "-12.50")
    tx.description = '=HYPERLINK("http://evil.internal","x")'
    tx.save()

    resp = cast(StreamingHttpResponse, client.get(f"{TX}export/"))
    body = b"".join(cast(Iterator[bytes], resp.streaming_content)).decode()
    header, row = list(csv.reader(io.StringIO(body)))

    assert header[5:] == ["amount", "currency", "description"]
    assert row[5] == "-12.50"
    assert row[7].startswith("'=")


def test_currency_is_validated_and_normalised(client: APIClient) -> None:
    ok = client.post(
        "/api/v1/accounts/", {"name": "W", "type": "cash", "currency": "usd"}, format="json"
    )
    assert ok.json()["currency"] == "USD"
    bad = client.post(
        "/api/v1/accounts/", {"name": "W", "type": "cash", "currency": "US1"}, format="json"
    )
    assert bad.status_code == 400


def test_tags_are_attached(client: APIClient, account: Any) -> None:
    tag = client.post("/api/v1/tags/", {"name": " Travel "}, format="json").json()
    assert tag["name"] == "travel"
    resp = client.post(
        TX,
        {
            "account": account.pk,
            "amount": "-1.00",
            "currency": "RUB",
            "occurred_at": "2026-04-01T12:00:00Z",
            "tags": [tag["id"]],
        },
        format="json",
    )
    assert resp.status_code == 201
    assert client.get(TX, {"tags": tag["id"]}).json()["count"] == 1
    assert Decimal(resp.json()["amount"]) == Decimal("-1.00")


CATEGORIES = "/api/v1/categories/"
TAGS = "/api/v1/tags/"


def test_category_names_are_unique_per_level(client: APIClient, user: Any) -> None:
    food = make_category(user, "Food")
    make_category(user, "Cafe", parent=food)

    root_dup = client.post(CATEGORIES, {"name": "Food", "kind": "expense"}, format="json")
    child_dup = client.post(
        CATEGORIES, {"name": "Cafe", "kind": "expense", "parent": food.pk}, format="json"
    )
    other_level = client.post(CATEGORIES, {"name": "Cafe", "kind": "expense"}, format="json")

    assert root_dup.status_code == 400
    assert child_dup.status_code == 400
    assert other_level.status_code == 201


def test_tag_names_are_unique_case_insensitively(client: APIClient) -> None:
    assert client.post(TAGS, {"name": "trip"}, format="json").status_code == 201
    dup = client.post(TAGS, {"name": " Trip "}, format="json")
    assert dup.status_code == 400
    assert dup.json()["code"] == "validation_error"


def test_category_with_live_children_cannot_be_deleted(client: APIClient, user: Any) -> None:
    food = make_category(user, "Food")
    cafe = make_category(user, "Cafe", parent=food)

    blocked = client.delete(f"{CATEGORIES}{food.pk}/")
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "category_has_children"

    assert client.delete(f"{CATEGORIES}{cafe.pk}/").status_code == 204
    assert client.delete(f"{CATEGORIES}{food.pk}/").status_code == 204


def test_transaction_keeps_its_deleted_category_on_update(
    client: APIClient, user: Any, account: Any
) -> None:
    old = make_category(user, "Old")
    tx = make_tx(account, "-5.00", category=old)
    client.delete(f"{CATEGORIES}{old.pk}/")

    body = client.get(f"{TX}{tx.pk}/").json()
    body["description"] = "edited"
    resp = client.put(f"{TX}{tx.pk}/", body, format="json")
    assert resp.status_code == 200
    assert resp.json()["category"] == old.pk

    # A different deleted category still cannot be attached.
    other = make_category(user, "Other")
    client.delete(f"{CATEGORIES}{other.pk}/")
    body["category"] = other.pk
    assert client.put(f"{TX}{tx.pk}/", body, format="json").status_code == 400


def test_transfer_that_converts_to_zero_is_rejected(client: APIClient, user: Any) -> None:
    rub = make_account(user, currency="RUB")
    usd = make_account(user, currency="USD")
    resp = client.post(
        TRANSFER,
        {
            "from_account": rub.pk,
            "to_account": usd.pk,
            "amount": "0.01",
            "fx_rate": "0.0001",
            "occurred_at": "2026-04-01T00:00:00Z",
        },
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "transfer_error"


def test_equal_timestamps_are_ordered_by_id(client: APIClient, user: Any) -> None:
    acc = make_account(user, opening="100.00")
    when = datetime(2026, 4, 1, tzinfo=UTC)
    ids = [make_tx(acc, "-1.00", when).pk for _ in range(3)]

    rows = client.get(TX, {"ordering": "occurred_at"}).json()["results"]
    assert [r["id"] for r in rows] == ids
    assert [r["running_balance"] for r in rows] == ["99.00", "98.00", "97.00"]

    rows = client.get(TX, {"ordering": "-occurred_at"}).json()["results"]
    assert [r["id"] for r in rows] == ids[::-1]


def test_transaction_currency_must_match_its_account(client: APIClient, user: Any) -> None:
    rub = make_account(user)
    usd = make_account(user, currency="USD")
    body = {
        "account": rub.pk,
        "amount": "-5.00",
        "currency": "USD",
        "occurred_at": "2026-04-01T00:00:00Z",
    }
    resp = client.post(TX, body, format="json")
    assert resp.status_code == 400
    assert resp.json()["detail"]["currency"] == ["must match the account currency (RUB)"]

    tx = make_tx(rub, "-5.00", datetime(2026, 4, 1, tzinfo=UTC))
    moved = client.patch(f"{TX}{tx.pk}/", {"account": usd.pk}, format="json")
    assert moved.status_code == 400
    assert "currency" in moved.json()["detail"]
