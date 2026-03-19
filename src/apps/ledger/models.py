from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class CategoryKind(models.TextChoices):
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"


class CategoryQuerySet(models.QuerySet["Category"]):
    def alive(self) -> CategoryQuerySet:
        return self.filter(is_deleted=False)


class Category(models.Model):
    """Two-level category hierarchy (parent → child, max depth 1).

    `parent` is a self-FK; serializer-level validation refuses deeper nesting.
    A user can have system-defined categories (`is_system=True`) which are
    seeded via data migration and shared across the catalogue.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="categories"
    )
    name = models.CharField(max_length=64)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    kind = models.CharField(max_length=16, choices=CategoryKind.choices)
    color = models.CharField(max_length=16, blank=True, default="")
    is_system = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CategoryQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "parent", "name"],
                condition=models.Q(is_deleted=False),
                name="category_unique_alive_per_parent",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "kind"],
                name="category_user_kind_alive_idx",
                condition=models.Q(is_deleted=False),
            ),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"


class TagQuerySet(models.QuerySet["Tag"]):
    def alive(self) -> TagQuerySet:
        return self.filter(is_deleted=False)


class Tag(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tags"
    )
    name = models.CharField(max_length=32)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TagQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                condition=models.Q(is_deleted=False),
                name="tag_unique_alive_per_user",
            ),
        ]
        ordering = ["name"]

    def save(self, *args, **kwargs) -> None:
        # Normalise to lowercase before write.
        self.name = self.name.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class TransactionType(models.TextChoices):
    REGULAR = "regular", "Regular"
    TRANSFER = "transfer", "Transfer"
    ADJUSTMENT = "adjustment", "Adjustment"


class TransactionQuerySet(models.QuerySet["Transaction"]):
    def alive(self) -> TransactionQuerySet:
        return self.filter(is_deleted=False)


class Transaction(models.Model):
    """One movement of money on a single account.

    Signed ``amount`` (positive = income, negative = expense). Currency may
    differ from the account's (relevant for cross-currency transfers).
    ``transfer_pair`` links the two legs of an inter-account transfer.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions"
    )
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="transactions"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    tags = models.ManyToManyField(Tag, related_name="transactions", blank=True)
    description = models.TextField(blank=True, default="")
    occurred_at = models.DateTimeField()
    type = models.CharField(
        max_length=16, choices=TransactionType.choices, default=TransactionType.REGULAR
    )
    transfer_pair = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    external_id = models.CharField(max_length=128, null=True, blank=True)
    import_hash = models.CharField(max_length=64, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TransactionQuerySet.as_manager()

    class Meta:
        constraints = [
            # Same (user, import_hash) shouldn't appear twice — protects CSV
            # re-imports from inserting duplicates. Partial unique keeps the
            # index small (only rows with a hash, which is < 30% in practice).
            models.UniqueConstraint(
                fields=["user", "import_hash"],
                condition=models.Q(import_hash__isnull=False),
                name="tx_user_import_hash_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "-occurred_at"],
                name="tx_user_occurred_alive_idx",
                condition=models.Q(is_deleted=False),
            ),
            models.Index(
                fields=["account", "occurred_at"],
                name="tx_account_occurred_alive_idx",
                condition=models.Q(is_deleted=False),
            ),
            models.Index(
                fields=["category"],
                name="tx_category_alive_idx",
                condition=models.Q(is_deleted=False),
            ),
            models.Index(
                fields=["external_id"],
                name="tx_external_id_idx",
                condition=models.Q(external_id__isnull=False),
            ),
        ]
        ordering = ["-occurred_at", "-id"]

    @property
    def signed_amount(self) -> Decimal:
        return self.amount

    def __str__(self) -> str:
        return f"{self.amount} {self.currency} on {self.occurred_at:%Y-%m-%d}"
