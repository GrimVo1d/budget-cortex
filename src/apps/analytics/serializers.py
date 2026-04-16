"""Response shapes of the report endpoints (read-only, built from query rows)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

_MONEY: dict[str, Any] = {"max_digits": 18, "decimal_places": 2, "read_only": True}


class CashflowRowSerializer(serializers.Serializer[Any]):
    month = serializers.DateField(read_only=True)
    currency = serializers.CharField(read_only=True)
    income = serializers.DecimalField(**_MONEY)
    expense = serializers.DecimalField(**_MONEY)
    net = serializers.DecimalField(**_MONEY)


class CategoryRowSerializer(serializers.Serializer[Any]):
    category_id = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    root_id = serializers.IntegerField(read_only=True)
    root_name = serializers.CharField(read_only=True)
    currency = serializers.CharField(read_only=True)
    total_expense = serializers.DecimalField(**_MONEY)


class OverrunRowSerializer(serializers.Serializer[Any]):
    budget_id = serializers.IntegerField(read_only=True)
    category_id = serializers.IntegerField(read_only=True, allow_null=True)
    currency = serializers.CharField(read_only=True)
    limit_amount = serializers.DecimalField(**_MONEY)
    spent_amount = serializers.DecimalField(**_MONEY)
    overrun_pct = serializers.FloatField(read_only=True)
