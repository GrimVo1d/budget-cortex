from __future__ import annotations

from decimal import Decimal

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.analytics.queries.running_balance import running_balances_for
from apps.core.mixins import UserScopedModelViewSet

from .filters import TransactionFilter
from .models import Category, Tag, Transaction
from .serializers import (
    CategorySerializer,
    TagSerializer,
    TransactionSerializer,
    TransferRequestSerializer,
)
from .services import TransferError, TransferRequest, create_transfer


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

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        from apps.analytics.exports import stream_csv

        qs = self.filter_queryset(self.get_queryset()).order_by("occurred_at", "id")
        header = [
            "id",
            "occurred_at",
            "account_id",
            "category_id",
            "type",
            "amount",
            "currency",
            "description",
        ]

        def rows():
            yield header
            for t in qs.iterator(chunk_size=1000):
                yield [
                    t.id,
                    t.occurred_at.isoformat(),
                    t.account_id,
                    t.category_id or "",
                    t.type,
                    str(t.amount),
                    t.currency,
                    t.description or "",
                ]

        return stream_csv(rows(), filename="transactions.csv")

    @action(detail=False, methods=["post"], url_path="transfer")
    def transfer(self, request):
        ser = TransferRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        try:
            from_acc = Account.objects.for_user(request.user.id).get(pk=d["from_account"])
            to_acc = Account.objects.for_user(request.user.id).get(pk=d["to_account"])
        except Account.DoesNotExist:
            return Response(
                {"code": "account_not_found", "detail": "account does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            debit, credit = create_transfer(
                TransferRequest(
                    user_id=request.user.id,
                    from_account=from_acc,
                    to_account=to_acc,
                    amount=d["amount"],
                    occurred_at=d["occurred_at"],
                    description=d.get("description", ""),
                    fx_rate=d.get("fx_rate"),
                )
            )
        except TransferError as exc:
            return Response(
                {"code": "transfer_error", "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "debit": TransactionSerializer(debit).data,
                "credit": TransactionSerializer(credit).data,
            },
            status=status.HTTP_201_CREATED,
        )
