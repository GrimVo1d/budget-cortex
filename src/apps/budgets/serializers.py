from __future__ import annotations

from rest_framework import serializers

from .models import Budget


class BudgetSerializer(serializers.ModelSerializer):
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

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("period_start", getattr(self.instance, "period_start", None))
        end = attrs.get("period_end", getattr(self.instance, "period_end", None))
        if start is not None and end is not None and end <= start:
            raise serializers.ValidationError(
                {"period_end": "period_end must be strictly greater than period_start"}
            )
        return attrs

    def validate_category(self, category):  # type: ignore[no-untyped-def]
        if category is None:
            return None
        request = self.context.get("request")
        if request is not None and category.user_id != request.user.id:
            raise serializers.ValidationError("category must belong to the same user")
        return category


class BudgetStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    category = serializers.IntegerField(allow_null=True)
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    currency = serializers.CharField()
    limit_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    spent_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    utilization = serializers.FloatField()
    is_over = serializers.BooleanField()
