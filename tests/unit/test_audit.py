from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.core.models import AuditAction, AuditLog

pytestmark = pytest.mark.django_db


def _jwt_client(anon: APIClient) -> APIClient:
    access = anon.post(
        "/api/v1/auth/token/", {"username": "alice", "password": "pw-12345"}, format="json"
    ).json()["access"]
    anon.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return anon


def test_jwt_request_records_actor_and_snapshots(anon: APIClient, user: Any) -> None:
    api = _jwt_client(anon)
    acc_id = api.post(
        "/api/v1/accounts/", {"name": "Card", "type": "debit", "currency": "RUB"}, format="json"
    ).json()["id"]
    api.patch(f"/api/v1/accounts/{acc_id}/", {"name": "Main card"}, format="json")
    api.delete(f"/api/v1/accounts/{acc_id}/")

    entries = list(AuditLog.objects.filter(model="accounts.Account").order_by("id"))

    assert [e.action for e in entries] == [
        AuditAction.CREATE,
        AuditAction.UPDATE,
        AuditAction.DELETE,
    ]
    assert {e.actor_id for e in entries} == {user.pk}
    assert entries[1].before["name"] == "Card"
    assert entries[1].after["name"] == "Main card"
    assert entries[2].after["is_deleted"] is True


def test_unaudited_models_are_ignored(client: APIClient) -> None:
    client.post("/api/v1/tags/", {"name": "x"}, format="json")
    assert not AuditLog.objects.exists()
