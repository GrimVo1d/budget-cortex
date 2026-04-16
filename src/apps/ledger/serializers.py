from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.accounts.models import Account
from apps.accounts.serializers import validate_currency_code
from apps.core.fields import OwnedPrimaryKeyRelatedField

from .models import Category, Tag, Transaction, TransactionType


class CategorySerializer(serializers.ModelSerializer[Category]):
    # ``parent`` shadows Field.parent for the type checker only; DRF pops
    # declared fields off the class, so there is no runtime clash.
    parent = OwnedPrimaryKeyRelatedField(Category, allow_null=True, required=False)  # type: ignore[assignment]

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "kind", "color", "is_system", "created_at"]
        read_only_fields = ["id", "is_system", "created_at"]

    def validate_parent(self, parent: Category | None) -> Category | None:
        if parent is not None and parent.parent_id is not None:
            raise serializers.ValidationError(
                "categories support only one level of nesting (parent must be a root)"
            )
        return parent

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance
        parent = attrs.get("parent", getattr(instance, "parent", None))
        name = attrs.get("name", getattr(instance, "name", None))
        request = self.context.get("request")
        if request is not None and name is not None:
            siblings = Category.objects.filter(
                user_id=request.user.pk, is_deleted=False, parent=parent, name=name
            )
            if instance is not None:
                siblings = siblings.exclude(pk=instance.pk)
            if siblings.exists():
                raise serializers.ValidationError(
                    {"name": "a category with this name already exists at this level"}
                )
        if isinstance(instance, Category) and parent is not None:
            if parent.pk == instance.pk:
                raise serializers.ValidationError({"parent": "category cannot be its own parent"})
            if instance.children.filter(is_deleted=False).exists():
                raise serializers.ValidationError(
                    {"parent": "a category with children cannot become a child"}
                )
        return attrs


class TagSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, name: str) -> str:
        name = name.strip().lower()  # the model normalises the same way on save
        request = self.context.get("request")
        if request is not None:
            same = Tag.objects.filter(user_id=request.user.pk, is_deleted=False, name=name)
            if self.instance is not None:
                same = same.exclude(pk=self.instance.pk)
            if same.exists():
                raise serializers.ValidationError("a tag with this name already exists")
        return name


class TransactionSerializer(serializers.ModelSerializer[Transaction]):
    account = OwnedPrimaryKeyRelatedField(Account)
    category = OwnedPrimaryKeyRelatedField(Category, allow_null=True, required=False)
    tags = OwnedPrimaryKeyRelatedField(Tag, many=True, required=False)
    type = serializers.ChoiceField(
        choices=[TransactionType.REGULAR, TransactionType.ADJUSTMENT],
        default=TransactionType.REGULAR,
    )
    running_balance = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "account",
            "amount",
            "currency",
            "category",
            "tags",
            "description",
            "occurred_at",
            "type",
            "transfer_pair",
            "external_id",
            "running_balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "transfer_pair",
            "external_id",
            "running_balance",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance: Transaction) -> dict[str, Any]:
        # Transfer legs are created by the transfer service; show their real type.
        data: dict[str, Any] = super().to_representation(instance)
        data["type"] = instance.type
        return data

    def get_running_balance(self, obj: Transaction) -> str | None:
        """Balance after this transaction, opening balance included.

        Filled in by the list endpoint (see ``running_balances_for``).
        """
        balances: dict[int, Decimal] = self.context.get("running_balances") or {}
        balance = balances.get(obj.pk)
        return None if balance is None else str(balance)

    def validate_currency(self, currency: str) -> str:
        return validate_currency_code(currency)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if (
            isinstance(self.instance, Transaction)
            and self.instance.type == TransactionType.TRANSFER
        ):
            raise serializers.ValidationError(
                "transfer legs cannot be edited; delete the transfer and create a new one"
            )
        return attrs


class TransferRequestSerializer(serializers.Serializer[None]):
    from_account = OwnedPrimaryKeyRelatedField(Account)
    to_account = OwnedPrimaryKeyRelatedField(Account)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    fx_rate = serializers.DecimalField(
        max_digits=20,
        decimal_places=10,
        min_value=Decimal("0.0000000001"),
        required=False,
        allow_null=True,
    )
    occurred_at = serializers.DateTimeField()
    description = serializers.CharField(required=False, allow_blank=True, default="")
