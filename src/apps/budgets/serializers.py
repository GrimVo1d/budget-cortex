from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.serializers import validate_currency_code
from apps.core.fields import OwnedPrimaryKeyRelatedField
from apps.ledger.models import Category

from .models import Budget


class BudgetSerializer(serializers.ModelSerializer[Budget]):
    category = OwnedPrimaryKeyRelatedField(Category, allow_null=True, required=False)

    class Meta:
        model = Budget
        fields = [
            "id",
            "category",
            "period",
            "period_start",
            "period_end",
            "limit_amount",
            "currency",
            "rollover",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"limit_amount": {"min_value": 0}}

    def validate_currency(self, currency: str) -> str:
        return validate_currency_code(currency)

    def _current(self, attrs: dict[str, Any], name: str) -> Any:
        return attrs[name] if name in attrs else getattr(self.instance, name, None)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = self._current(attrs, "period_start")
        end = self._current(attrs, "period_end")
        if start is not None and end is not None and end <= start:
            raise serializers.ValidationError(
                {"period_end": "period_end must be strictly greater than period_start"}
            )

        # Two live budgets for the same (category, currency) must not overlap.
        # PostgreSQL also enforces this with an exclusion constraint.
        request = self.context.get("request")
        if request is not None and start is not None and end is not None:
            overlapping = Budget.objects.filter(
                user_id=request.user.pk,
                is_deleted=False,
                category=self._current(attrs, "category"),
                currency=self._current(attrs, "currency"),
                period_start__lt=end,
                period_end__gt=start,
            )
            if self.instance is not None:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise serializers.ValidationError(
                    "overlaps another budget for the same category and currency"
                )
        return attrs


class BudgetStatusSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    category = serializers.IntegerField(allow_null=True)
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    currency = serializers.CharField()
    limit_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    # Computed values: a sum of many amounts or a ratio to a tiny limit can
    # outgrow any column width, so no max_digits (it would raise on output).
    spent_amount = serializers.DecimalField(max_digits=None, decimal_places=2)
    remaining_amount = serializers.DecimalField(max_digits=None, decimal_places=2)
    utilization = serializers.DecimalField(max_digits=None, decimal_places=4, allow_null=True)
    is_over = serializers.BooleanField()
