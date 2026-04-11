"""BRIN index on transactions.occurred_at for historic range scans.

BRIN is ~1000x smaller than B-tree on large append-mostly tables ordered
by time. It loses tuple-level precision but pays it back on full-month
or multi-year range queries that hit huge contiguous blocks.

PostgreSQL-only — on SQLite the operation is a no-op so the test suite
can still apply the migration chain.
"""

from __future__ import annotations

from django.db import migrations

SQL = (
    "CREATE INDEX IF NOT EXISTS tx_occurred_at_brin "
    "ON ledger_transaction USING BRIN (occurred_at) "
    "WITH (pages_per_range = 32);"
)
REVERSE_SQL = "DROP INDEX IF EXISTS tx_occurred_at_brin;"


def forward(apps, schema_editor):  # type: ignore[no-untyped-def]
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def reverse(apps, schema_editor):  # type: ignore[no-untyped-def]
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0003_transaction_tx_user_import_hash_unique"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
