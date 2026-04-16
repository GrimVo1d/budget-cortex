from __future__ import annotations

from django_filters import rest_framework as filters

from apps.accounts.models import Account
from apps.core.fields import owned

from .models import Category, Tag, Transaction


class CategoryFilter(filters.FilterSet):
    parent = filters.ModelChoiceFilter(queryset=lambda request: owned(Category, request))

    class Meta:
        model = Category
        fields = ["kind", "parent"]


class TransactionFilter(filters.FilterSet):
    account = filters.ModelChoiceFilter(queryset=lambda request: owned(Account, request))
    category = filters.ModelChoiceFilter(queryset=lambda request: owned(Category, request))
    tags = filters.ModelMultipleChoiceFilter(queryset=lambda request: owned(Tag, request))
    occurred_from = filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="gte")
    occurred_to = filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="lte")
    amount_min = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    q = filters.CharFilter(field_name="description", lookup_expr="icontains")

    class Meta:
        model = Transaction
        fields = ["account", "category", "type", "currency", "tags"]
