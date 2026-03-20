from __future__ import annotations

from decimal import Decimal

from rest_framework.response import Response

from apps.analytics.queries.running_balance import running_balances_for
from apps.core.mixins import UserScopedModelViewSet

from .filters import TransactionFilter
from .models import Category, Tag, Transaction
from .serializers import CategorySerializer, TagSerializer, TransactionSerializer


class CategoryViewSet(UserScopedModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filterset_fields = ["kind", "parent"]
    ordering_fields = ["name", "created_at"]


class TagViewSet(UserScopedModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    ordering_fields = ["name", "created_at"]


class TransactionViewSet(UserScopedModelViewSet):
    queryset = Transaction.objects.all().select_related("account", "category")
    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter
    ordering_fields = ["occurred_at", "amount", "created_at"]

    def list(self, request, *args, **kwargs):  # type: ignore[override]
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        items = list(page) if page is not None else list(qs)
        data = self.get_serializer(items, many=True).data

        if items:
            cumulative = running_balances_for(items, request.user.id)
            opening_by_account = {it.account_id: it.account.opening_balance for it in items}
            for row, item in zip(items, data, strict=True):
                cum = cumulative.get(row.id)
                if cum is None:
                    item["running_balance"] = None
                else:
                    bal = Decimal(opening_by_account[row.account_id]) + cum
                    item["running_balance"] = str(bal)

        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)
