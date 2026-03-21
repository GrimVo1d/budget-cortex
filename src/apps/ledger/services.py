"""Domain services for the ledger.

Atomic transfer is the canonical use case: a single user-intent translates to
two physical :class:`Transaction` rows on different accounts, linked via
``transfer_pair``. We wrap them in ``transaction.atomic`` so a failure on the
second leg rolls back the first — never leaves orphan money.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import transaction

from apps.accounts.models import Account

from .models import Transaction, TransactionType


class TransferError(Exception):
    """Raised when transfer inputs are invalid (currency mismatch w/o rate, etc.)."""


@dataclass(frozen=True)
class TransferRequest:
    user_id: int
    from_account: Account
    to_account: Account
    amount: Decimal  # positive — direction is implied by from/to
    occurred_at: datetime
    description: str = ""
    fx_rate: Decimal | None = None


def create_transfer(req: TransferRequest) -> tuple[Transaction, Transaction]:
    """Create two paired :class:`Transaction` rows in a single DB transaction.

    Returns the (debit_leg, credit_leg) tuple. If currencies match, ``fx_rate``
    is ignored. If currencies differ, ``fx_rate`` is required.
    """
    if req.from_account.id == req.to_account.id:
        raise TransferError("from_account and to_account must differ")
    if req.amount <= Decimal("0"):
        raise TransferError("amount must be positive")
    if req.from_account.user_id != req.user_id or req.to_account.user_id != req.user_id:
        raise TransferError("both accounts must belong to the requesting user")

    cross_currency = req.from_account.currency != req.to_account.currency
    if cross_currency and req.fx_rate is None:
        raise TransferError(
            f"fx_rate is required for cross-currency transfer "
            f"({req.from_account.currency} → {req.to_account.currency})"
        )
    credit_amount = req.amount * req.fx_rate if cross_currency else req.amount

    with transaction.atomic():
        debit = Transaction.objects.create(
            user_id=req.user_id,
            account=req.from_account,
            amount=-req.amount,
            currency=req.from_account.currency,
            description=req.description,
            occurred_at=req.occurred_at,
            type=TransactionType.TRANSFER,
        )
        credit = Transaction.objects.create(
            user_id=req.user_id,
            account=req.to_account,
            amount=credit_amount,
            currency=req.to_account.currency,
            description=req.description,
            occurred_at=req.occurred_at,
            type=TransactionType.TRANSFER,
            transfer_pair=debit,
        )
        # Link debit → credit too (deferred FK set after credit exists).
        debit.transfer_pair = credit
        debit.save(update_fields=["transfer_pair", "updated_at"])
    return debit, credit
