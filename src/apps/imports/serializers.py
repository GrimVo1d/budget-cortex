from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import Account
from apps.core.fields import OwnedPrimaryKeyRelatedField

from .models import CsvImport


class CsvImportSerializer(serializers.ModelSerializer[CsvImport]):
    account = OwnedPrimaryKeyRelatedField(Account)
    file = serializers.FileField(write_only=True)

    class Meta:
        model = CsvImport
        fields = [
            "id",
            "account",
            "fmt",
            "file",
            "status",
            "error",
            "rows_total",
            "rows_inserted",
            "rows_skipped",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "error",
            "rows_total",
            "rows_inserted",
            "rows_skipped",
            "created_at",
            "updated_at",
        ]
