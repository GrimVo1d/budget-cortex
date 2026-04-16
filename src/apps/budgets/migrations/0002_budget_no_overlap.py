"""Forbid overlapping live budgets per (user, category, currency).

GiST exclusion constraint over ``tstzrange(period_start, period_end)``.
``btree_gist`` provides the ``=`` operator class for the scalar columns;
it is a trusted extension, so the database owner can create it.
``category_id`` is COALESCEd so "all categories" budgets (NULL) also
conflict with each other.

PostgreSQL-only: on SQLite the operation is a no-op and the serializer's
overlap check is the only guard.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

FORWARD = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist;",
    """
    ALTER TABLE budgets_budget
    ADD CONSTRAINT budget_no_overlap
    EXCLUDE USING gist (
        user_id WITH =,
        (COALESCE(category_id, 0)) WITH =,
        currency WITH =,
        tstzrange(period_start, period_end, '[)') WITH &&
    ) WHERE (NOT is_deleted);
    """,
]
REVERSE = ["ALTER TABLE budgets_budget DROP CONSTRAINT IF EXISTS budget_no_overlap;"]


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
        ("budgets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
