"""Tiny model factories shared by the test suite."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from apps.accounts.models import Account, AccountType
from apps.ledger.models import Category, CategoryKind, Transaction


def make_account(
    user: Any, currency: str = "RUB", opening: str = "0", name: str = "Cash"
) -> Account:
    return Account.objects.create(
        user=user,
        name=name,
        type=AccountType.CASH,
        currency=currency,
        opening_balance=Decimal(opening),
    )


def make_category(
    user: Any, name: str = "Food", kind: str = CategoryKind.EXPENSE, parent: Category | None = None
) -> Category:
    return Category.objects.create(user=user, name=name, kind=kind, parent=parent)


def make_tx(
    account: Account,
    amount: str,
    when: datetime | None = None,
    category: Category | None = None,
    currency: str | None = None,
) -> Transaction:
    return Transaction.objects.create(
        user_id=account.user_id,
        account=account,
        amount=Decimal(amount),
        currency=currency or account.currency,
        category=category,
        occurred_at=when or datetime(2026, 4, 1, 12, tzinfo=UTC),
    )
