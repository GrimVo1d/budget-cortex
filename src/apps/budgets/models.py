"""Spending limit for a (category, period) tuple.

Storage uses two ``timestamptz`` columns ``period_start`` / ``period_end``
treated as a half-open range ``[start, end)``. On PostgreSQL migration 0002
adds a GiST exclusion constraint over ``tstzrange(period_start, period_end)``
so two live budgets for the same (user, category, currency) can never
overlap; the serializer runs the same check portably for a clean 400.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class BudgetPeriod(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    WEEKLY = "weekly", "Weekly"
    CUSTOM = "custom", "Custom"


class BudgetQuerySet(models.QuerySet["Budget"]):
    def alive(self) -> BudgetQuerySet:
        return self.filter(is_deleted=False)


class Budget(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="budgets"
    )
    category = models.ForeignKey(
        "ledger.Category",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="budgets",
    )
    period = models.CharField(max_length=16, choices=BudgetPeriod.choices)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    limit_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    rollover = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BudgetQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "category"],
                name="budget_user_cat_alive_idx",
                condition=models.Q(is_deleted=False),
            ),
            # Portable B-tree for range scans; the PG-only GiST exclusion
            # constraint lives in migration 0002.
            models.Index(
                fields=["period_start", "period_end"],
                name="budget_period_range_idx",
                condition=models.Q(is_deleted=False),
            ),
        ]
        ordering = ["-period_start"]

    def __str__(self) -> str:
        cat = self.category.name if self.category_id and self.category else "—"
        return f"Budget({cat}, {self.limit_amount} {self.currency})"
