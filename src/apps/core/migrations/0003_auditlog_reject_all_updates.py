"""Close the actor loophole in the append-only audit trigger.

0002 let one UPDATE through: ``actor_id`` set to NULL with every other column
unchanged, meant for Django's emulated ``ON DELETE SET NULL``. Nothing tied it
to a user deletion, so any code path could strip attribution from a row. The
actor is now ``PROTECT`` and the trigger rejects every UPDATE and DELETE.

The function also pins ``search_path``, so a session cannot shadow the
operators it uses with objects from its own schema.

PostgreSQL-only: on SQLite only the field change applies (it is not a schema
change there either; ``on_delete`` lives in Django).
"""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

FORWARD = """
CREATE OR REPLACE FUNCTION core_auditlog_append_only() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION USING
        MESSAGE = 'audit log is append-only (' || TG_OP || ' refused)',
        ERRCODE = 'restrict_violation';
END
$$;
"""

# The 0002 body, restored on rollback.
REVERSE = """
CREATE OR REPLACE FUNCTION core_auditlog_append_only() RETURNS trigger
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
"""


def forward(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD)


def reverse(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_auditlog_append_only"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="actor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(forward, reverse),
    ]
