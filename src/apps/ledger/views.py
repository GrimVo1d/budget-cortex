from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.analytics.queries.running_balance import running_balances_for
from apps.core.auth import user_id
from apps.core.csv import stream_csv
from apps.core.exceptions import ApiError
from apps.core.mixins import UserScopedModelViewSet

from .filters import CategoryFilter, TransactionFilter
from .models import Category, Tag, Transaction, TransactionType
from .serializers import (
    CategorySerializer,
    TagSerializer,
    TransactionSerializer,
    TransferRequestSerializer,
)
from .services import TransferError, TransferRequest, create_transfer, delete_transfer


class CategoryViewSet(UserScopedModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filterset_class = CategoryFilter
    ordering_fields = ["name", "created_at"]

    def perform_destroy(self, instance: Category) -> None:
        if instance.children.filter(is_deleted=False).exists():
            raise ApiError(
                "delete or move the child categories first", code="category_has_children"
            )
        super().perform_destroy(instance)


class TagViewSet(UserScopedModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    ordering_fields = ["name", "created_at"]


class TransactionViewSet(UserScopedModelViewSet):
    queryset = Transaction.objects.select_related("account").prefetch_related("tags")
    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter
    ordering_fields = ["occurred_at", "amount", "created_at"]

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        items: list[Transaction] = list(page) if page is not None else list(qs)

        cumulative = running_balances_for([tx.pk for tx in items], user_id(request))
        balances = {
            tx.pk: tx.account.opening_balance + cumulative[tx.pk]
            for tx in items
            if tx.pk in cumulative
        }
        context = {**self.get_serializer_context(), "running_balances": balances}
        data = TransactionSerializer(items, many=True, context=context).data

        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

    def perform_destroy(self, instance: Transaction) -> None:
        if instance.type == TransactionType.TRANSFER:
            delete_transfer(instance)
        else:
            super().perform_destroy(instance)

    @extend_schema(responses={200: OpenApiResponse(description="CSV file")})
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request: Request) -> StreamingHttpResponse:
        qs: QuerySet[Transaction] = self.filter_queryset(self.get_queryset()).order_by(
            "occurred_at", "id"
        )
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

        def rows() -> Iterator[list[Any]]:
            yield header
            for t in qs.iterator(chunk_size=1000):
                yield [
                    t.pk,
                    t.occurred_at.isoformat(),
                    t.account_id,
                    t.category_id or "",
                    t.type,
                    t.amount,
                    t.currency,
                    t.description,
                ]

        return stream_csv(rows(), filename="transactions.csv")

    @extend_schema(
        request=TransferRequestSerializer,
        responses={201: OpenApiResponse(description="Debit and credit legs")},
    )
    @action(detail=False, methods=["post"], url_path="transfer")
    def transfer(self, request: Request) -> Response:
        ser = TransferRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        try:
            debit, credit = create_transfer(
                TransferRequest(
                    user_id=user_id(request),
                    from_account=d["from_account"],
                    to_account=d["to_account"],
                    amount=d["amount"],
                    occurred_at=d["occurred_at"],
                    description=d.get("description", ""),
                    fx_rate=d.get("fx_rate"),
                )
            )
        except TransferError as exc:
            raise ApiError(str(exc), code="transfer_error") from exc

        context = self.get_serializer_context()
        return Response(
            {
                "debit": TransactionSerializer(debit, context=context).data,
                "credit": TransactionSerializer(credit, context=context).data,
            },
            status=status.HTTP_201_CREATED,
        )
