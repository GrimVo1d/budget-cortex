"""Cross-user isolation: another user's ids behave exactly like missing ids."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.ledger.models import Tag, Transaction
from tests.factories import make_account, make_category

pytestmark = pytest.mark.django_db

TX = "/api/v1/transactions/"


def _tx_payload(account_id: int, **extra: Any) -> dict[str, Any]:
    return {
        "account": account_id,
        "amount": "-10.00",
        "currency": "RUB",
        "occurred_at": "2026-04-01T12:00:00Z",
        **extra,
    }


def test_foreign_tag_is_rejected_like_missing_one(
    client: APIClient, account: Any, other_user: Any
) -> None:
    foreign = Tag.objects.create(user=other_user, name="secret")
    foreign_resp = client.post(TX, _tx_payload(account.pk, tags=[foreign.pk]), format="json")
    missing_resp = client.post(TX, _tx_payload(account.pk, tags=[foreign.pk + 1000]), format="json")

    assert foreign_resp.status_code == missing_resp.status_code == 400
    assert "does not exist" in str(foreign_resp.json()["detail"]["tags"])
    assert not Transaction.objects.exists()


@pytest.mark.parametrize("field", ["account", "category"])
def test_foreign_account_and_category_are_rejected(
    client: APIClient, account: Any, other_user: Any, field: str
) -> None:
    foreign = make_account(other_user) if field == "account" else make_category(other_user)
    payload = _tx_payload(account.pk, **{field: foreign.pk})
    resp = client.post(TX, payload, format="json")
    assert resp.status_code == 400
    assert "does not exist" in str(resp.json()["detail"][field])


def test_soft_deleted_account_cannot_be_referenced(client: APIClient, account: Any) -> None:
    assert client.delete(f"/api/v1/accounts/{account.pk}/").status_code == 204
    resp = client.post(TX, _tx_payload(account.pk), format="json")
    assert resp.status_code == 400


def test_foreign_object_detail_is_404(client: APIClient, other_user: Any) -> None:
    foreign = make_account(other_user)
    resp = client.get(f"/api/v1/accounts/{foreign.pk}/")
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_filter_by_foreign_account_matches_missing_account(
    client: APIClient, account: Any, other_user: Any
) -> None:
    foreign = make_account(other_user)
    foreign_resp = client.get(TX, {"account": foreign.pk})
    missing_resp = client.get(TX, {"account": foreign.pk + 1000})
    assert foreign_resp.status_code == missing_resp.status_code == 400


def test_category_parent_must_be_own(client: APIClient, other_user: Any) -> None:
    foreign = make_category(other_user)
    resp = client.post(
        "/api/v1/categories/", {"name": "x", "kind": "expense", "parent": foreign.pk}, format="json"
    )
    assert resp.status_code == 400
