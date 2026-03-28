from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import UserScopedModelViewSet
from apps.ledger.models import Transaction, TransactionType

from .models import Budget
from .serializers import BudgetSerializer, BudgetStatusSerializer


class BudgetViewSet(UserScopedModelViewSet):
    queryset = Budget.objects.all().select_related("category")
    serializer_class = BudgetSerializer
    filterset_fields = ["category", "period", "currency"]
    ordering_fields = ["period_start", "limit_amount", "created_at"]

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):  # type: ignore[no-untyped-def]
        budget: Budget = self.get_object()

        spent_filter = Q(
            user_id=request.user.id,
            occurred_at__gte=budget.period_start,
            occurred_at__lt=budget.period_end,
            type=TransactionType.EXPENSE,
            is_deleted=False,
        )
        if budget.category_id is not None:
            spent_filter &= Q(category_id=budget.category_id) | Q(
                category__parent_id=budget.category_id
            )

        agg = Transaction.objects.filter(spent_filter).aggregate(total=Sum("amount"))
        raw_total = agg["total"] or Decimal("0")
        spent = abs(raw_total)
        limit = Decimal(budget.limit_amount)
        remaining = limit - spent
        utilization = float(spent / limit) if limit > 0 else 0.0

        payload = {
            "id": budget.id,
            "category": budget.category_id,
            "period_start": budget.period_start,
            "period_end": budget.period_end,
            "currency": budget.currency,
            "limit_amount": limit,
            "spent_amount": spent,
            "remaining_amount": remaining,
            "utilization": round(utilization, 4),
            "is_over": spent > limit,
        }
        return Response(BudgetStatusSerializer(payload).data)
