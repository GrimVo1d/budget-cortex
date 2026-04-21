from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, Sum
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.fields import owned
from apps.core.mixins import UserScopedModelViewSet
from apps.ledger.models import Category, CategoryKind, Transaction

from .models import Budget
from .serializers import BudgetSerializer, BudgetStatusSerializer


class BudgetFilter(filters.FilterSet):
    category = filters.ModelChoiceFilter(queryset=lambda request: owned(Category, request))

    class Meta:
        model = Budget
        fields = ["category", "period", "currency"]


class BudgetViewSet(UserScopedModelViewSet):
    queryset = Budget.objects.select_related("category")
    serializer_class = BudgetSerializer
    filterset_class = BudgetFilter
    ordering_fields = ["period_start", "limit_amount", "created_at"]

    @extend_schema(responses=BudgetStatusSerializer)
    @action(detail=True, methods=["get"])
    def status(self, request: Request, pk: str | None = None) -> Response:
        """Live spend against the limit, straight from transactions (no MV lag).

        Counts expense-kind transactions in the budget currency within
        ``[period_start, period_end)``; a category budget includes its children.
        """
        budget: Budget = self.get_object()

        spent_filter = Q(
            user_id=request.user.pk,
            currency=budget.currency,
            occurred_at__gte=budget.period_start,
            occurred_at__lt=budget.period_end,
            category__kind=CategoryKind.EXPENSE,
            is_deleted=False,
        )
        if budget.category_id is not None:
            spent_filter &= Q(category_id=budget.category_id) | Q(
                category__parent_id=budget.category_id
            )

        total = Transaction.objects.filter(spent_filter).aggregate(total=Sum("amount"))["total"]
        spent = abs(total or Decimal("0"))
        limit = budget.limit_amount
        # A share of the limit, exact like the amounts; undefined for a zero limit.
        utilization = (spent / limit).quantize(Decimal("0.0001")) if limit > 0 else None

        payload = {
            "id": budget.pk,
            "category": budget.category_id,
            "period_start": budget.period_start,
            "period_end": budget.period_end,
            "currency": budget.currency,
            "limit_amount": limit,
            "spent_amount": spent,
            "remaining_amount": limit - spent,
            "utilization": utilization,
            "is_over": spent > limit,
        }
        return Response(BudgetStatusSerializer(payload).data)
