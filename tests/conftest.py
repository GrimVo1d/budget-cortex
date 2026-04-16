from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Account
from tests.factories import make_account

User = get_user_model()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if "postgresql" in settings.DATABASES["default"]["ENGINE"]:
        return
    skip = pytest.mark.skip(reason="needs PostgreSQL (make test-pg)")
    for item in items:
        if "requires_postgres" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _media_root(settings: Any, tmp_path: Path) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def user(db: None) -> Any:
    return User.objects.create_user(
        username="alice", email="alice@mail.internal", password="pw-12345"
    )


@pytest.fixture
def other_user(db: None) -> Any:
    return User.objects.create_user(username="bob", email="bob@mail.internal", password="pw-12345")


@pytest.fixture
def client(user: Any) -> APIClient:
    api = APIClient()
    api.force_authenticate(user)
    return api


@pytest.fixture
def anon() -> APIClient:
    return APIClient()


@pytest.fixture
def account(user: Any) -> Account:
    return make_account(user)
