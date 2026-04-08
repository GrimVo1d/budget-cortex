from __future__ import annotations

import django
import pytest
from django.contrib.auth import get_user_model


def pytest_configure(config):  # type: ignore[no-untyped-def]
    django.setup()


@pytest.fixture
def user(db):  # type: ignore[no-untyped-def]
    User = get_user_model()
    return User.objects.create_user(username="alice", password="pw-12345")


@pytest.fixture
def account(db, user):  # type: ignore[no-untyped-def]
    from apps.accounts.models import Account, AccountType

    return Account.objects.create(
        user=user,
        name="Cash",
        type=AccountType.CASH,
        currency="RUB",
        opening_balance="0",
    )
