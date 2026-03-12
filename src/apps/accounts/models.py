from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class AccountType(models.TextChoices):
    CASH = "cash", "Cash"
    DEBIT = "debit", "Debit card"
    CREDIT = "credit", "Credit card"
    SAVINGS = "savings", "Savings"


class AccountQuerySet(models.QuerySet["Account"]):
    def alive(self) -> AccountQuerySet:
        return self.filter(is_deleted=False)

    def for_user(self, user_id: int) -> AccountQuerySet:
        return self.alive().filter(user_id=user_id)


class Account(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accounts"
    )
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=AccountType.choices)
    currency = models.CharField(max_length=3)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    is_archived = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AccountQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(
                fields=["user"],
                name="account_user_alive_idx",
                condition=models.Q(is_deleted=False),
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.currency})"
