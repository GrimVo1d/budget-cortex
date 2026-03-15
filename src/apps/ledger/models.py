from __future__ import annotations

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
