from __future__ import annotations

from django_filters import rest_framework as filters

from .models import Transaction


class TransactionFilter(filters.FilterSet):
    occurred_from = filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="gte")
    occurred_to = filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="lte")
    amount_min = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    q = filters.CharFilter(field_name="description", lookup_expr="icontains")

    class Meta:
        model = Transaction
        fields = ["account", "category", "type", "currency", "tags"]
