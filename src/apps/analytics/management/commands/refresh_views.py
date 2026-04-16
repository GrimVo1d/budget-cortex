from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from tasks.analytics import refresh_materialized_views


class Command(BaseCommand):
    help = "Refresh the analytics materialized views now (PostgreSQL only)."

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            raise CommandError("materialized views exist only on PostgreSQL")
        for view, result in refresh_materialized_views.run().items():
            self.stdout.write(f"{view}: {result}")
