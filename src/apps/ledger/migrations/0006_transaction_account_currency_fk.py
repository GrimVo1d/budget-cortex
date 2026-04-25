"""Tie a transaction's currency to its account's in the database.

The serializers check that a transaction is in its account's currency and
that a used account keeps its currency, but two concurrent requests (or an
import running while the account is edited) can each pass their check. A
composite foreign key ``(account_id, currency) -> accounts_account (id,
currency)`` closes that race: the insert of a mismatched row fails, and so
does changing the currency of an account that any transaction (deleted ones
included) refers to. The error surfaces as ``IntegrityError`` (409, or a
failed import).

``NOT VALID`` keeps rows written before the rule (they are not rewritten);
new and updated rows are checked. ``VALIDATE CONSTRAINT`` can run once the old
data is clean.

PostgreSQL-only: on SQLite the operation is a no-op and the serializers are
the only guard.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

FORWARD = [
    "ALTER TABLE accounts_account ADD CONSTRAINT account_id_currency_uniq UNIQUE (id, currency);",
    """
    ALTER TABLE ledger_transaction
    ADD CONSTRAINT tx_account_currency_fk
    FOREIGN KEY (account_id, currency) REFERENCES accounts_account (id, currency)
    ON UPDATE RESTRICT ON DELETE RESTRICT
    NOT VALID;
    """,
]
REVERSE = [
    "ALTER TABLE ledger_transaction DROP CONSTRAINT IF EXISTS tx_account_currency_fk;",
    "ALTER TABLE accounts_account DROP CONSTRAINT IF EXISTS account_id_currency_uniq;",
]


def forward(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor == "postgresql":
        for sql in FORWARD:
            schema_editor.execute(sql)


def reverse(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor == "postgresql":
        for sql in REVERSE:
            schema_editor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("ledger", "0005_category_unique_alive_root"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
