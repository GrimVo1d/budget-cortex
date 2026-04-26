from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from tasks.auth import flush_expired_tokens

REGISTER = "/api/v1/auth/register/"
TOKEN = "/api/v1/auth/token/"
REFRESH = "/api/v1/auth/token/refresh/"
LOGOUT = "/api/v1/auth/logout/"

pytestmark = pytest.mark.django_db


def _register(anon: APIClient, **overrides: str) -> Any:
    payload = {"username": "carol", "email": "carol@mail.internal", "password": "Long-enough-pw-42"}
    payload.update(overrides)
    return anon.post(REGISTER, payload, format="json")


def test_register_and_obtain_token(anon: APIClient) -> None:
    assert _register(anon).status_code == 201
    resp = anon.post(TOKEN, {"username": "carol", "password": "Long-enough-pw-42"}, format="json")
    assert resp.status_code == 200
    assert {"access", "refresh"} <= set(resp.json())


def test_register_rejects_duplicate_email_case_insensitive(anon: APIClient, user: Any) -> None:
    resp = _register(anon, email="ALICE@mail.internal")
    assert resp.status_code == 400
    assert resp.json()["code"] == "validation_error"
    assert "email" in resp.json()["detail"]


def test_register_rejects_password_similar_to_username(anon: APIClient) -> None:
    resp = _register(anon, username="carolinedoe", password="carolinedoe1")
    assert resp.status_code == 400
    assert "non_field_errors" in resp.json()["detail"]


def test_refresh_rotates_and_logout_blacklists(anon: APIClient, user: Any) -> None:
    tokens = anon.post(TOKEN, {"username": "alice", "password": "pw-12345"}, format="json").json()

    rotated = anon.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert rotated.status_code == 200
    assert rotated.json()["refresh"] != tokens["refresh"]
    # The old refresh token is blacklisted after rotation.
    assert anon.post(REFRESH, {"refresh": tokens["refresh"]}, format="json").status_code == 401

    new_refresh = rotated.json()["refresh"]
    assert anon.post(LOGOUT, {"refresh": new_refresh}, format="json").status_code == 200
    blacklisted = anon.post(REFRESH, {"refresh": new_refresh}, format="json")
    assert blacklisted.status_code == 401
    assert blacklisted.json() == {"code": "token_not_valid", "detail": "Token is blacklisted"}


def test_token_endpoint_is_throttled(anon: APIClient, user: Any) -> None:
    codes = [
        anon.post(TOKEN, {"username": "alice", "password": "wrong"}, format="json").status_code
        for _ in range(12)
    ]
    assert codes[:10] == [401] * 10
    assert codes[-1] == 429


def test_throttle_ignores_spoofed_forwarded_for(anon: APIClient, user: Any) -> None:
    codes = [
        anon.post(
            TOKEN,
            {"username": "alice", "password": "wrong"},
            format="json",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{i}",
        ).status_code
        for i in range(12)
    ]
    assert codes[-1] == 429


def test_flush_task_drops_only_expired_tokens(anon: APIClient, user: Any) -> None:
    for _ in range(2):
        anon.post(TOKEN, {"username": "alice", "password": "pw-12345"}, format="json")
    stale = OutstandingToken.objects.order_by("id").first()
    assert stale is not None
    OutstandingToken.objects.filter(pk=stale.pk).update(
        expires_at=timezone.now() - timedelta(days=1)
    )
    flush_expired_tokens.delay()
    assert OutstandingToken.objects.count() == 1
    assert not OutstandingToken.objects.filter(pk=stale.pk).exists()


def test_deactivated_user_loses_access_and_refresh(anon: APIClient, user: Any) -> None:
    tokens = anon.post(TOKEN, {"username": "alice", "password": "pw-12345"}, format="json").json()
    user.is_active = False
    user.save()

    anon.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert anon.get("/api/v1/accounts/").status_code == 401
    anon.credentials()
    assert anon.post(REFRESH, {"refresh": tokens["refresh"]}, format="json").status_code == 401


def test_api_requires_authentication(anon: APIClient) -> None:
    resp = anon.get("/api/v1/accounts/")
    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"


def test_health_endpoints(anon: APIClient) -> None:
    assert anon.get("/health/live").json() == {"status": "ok"}
    ready = anon.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["database"] == "ok"


def test_openapi_schema_is_served(anon: APIClient) -> None:
    resp = anon.get("/api/schema/")
    assert resp.status_code == 200
    assert b"/api/v1/transactions/transfer/" in resp.content
