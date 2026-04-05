"""CSV import job state.

A single :class:`CsvImport` row tracks one uploaded file from creation
through parsing to either ``done`` or ``failed``. The ``file_hash``
(sha256 of the raw bytes) is unique per user, making re-uploads of the
same file no-ops.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class ImportStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PARSING = "parsing", "Parsing"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


class ImportFormat(models.TextChoices):
    GENERIC = "generic", "Generic"
    TINKOFF = "tinkoff", "Tinkoff"
    SBERBANK = "sberbank", "Sberbank"


class CsvImport(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="csv_imports"
    )
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="csv_imports"
    )
    fmt = models.CharField(max_length=16, choices=ImportFormat.choices)
    file_path = models.CharField(max_length=512)
    file_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16, choices=ImportStatus.choices, default=ImportStatus.PENDING
    )
    error = models.TextField(blank=True, default="")
    rows_total = models.IntegerField(default=0)
    rows_inserted = models.IntegerField(default=0)
    rows_skipped = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "file_hash"], name="import_user_filehash_unique"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="import_user_status_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"CsvImport(#{self.id}, {self.fmt}, {self.status})"
