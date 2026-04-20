"""Make the audit log append-only in the database.

A row-level trigger rejects UPDATE and DELETE on ``core_auditlog``, so a bug
or a stray ``QuerySet.update()`` in the application cannot rewrite history.
The one update it lets through is the ``ON DELETE SET NULL`` that Django runs
on ``actor_id`` when the acting user is deleted: every other column must stay
the same. The error is a ``restrict_violation``, which surfaces as
``IntegrityError``.

The trigger does not stop the table owner: TRUNCATE (used by test teardown)
and dropping the trigger stay possible, see ARCHITECTURE "Accepted risks".

PostgreSQL-only: on SQLite the operation is a no-op.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

FORWARD = [
    """
    CREATE FUNCTION core_auditlog_append_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'UPDATE'
           AND NEW.actor_id IS NULL
           AND to_jsonb(NEW) - 'actor_id' = to_jsonb(OLD) - 'actor_id' THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION USING
            MESSAGE = 'audit log is append-only (' || TG_OP || ' refused)',
            ERRCODE = 'restrict_violation';
    END
    $$;
    """,
    """
    CREATE TRIGGER auditlog_append_only
    BEFORE UPDATE OR DELETE ON core_auditlog
    FOR EACH ROW EXECUTE FUNCTION core_auditlog_append_only();
    """,
]
REVERSE = [
    "DROP TRIGGER IF EXISTS auditlog_append_only ON core_auditlog;",
    "DROP FUNCTION IF EXISTS core_auditlog_append_only();",
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
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
