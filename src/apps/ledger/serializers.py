from __future__ import annotations

from rest_framework import serializers

from .models import Category, Tag, Transaction


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent", "kind", "color", "is_system", "created_at"]
        read_only_fields = ["id", "is_system", "created_at"]

    def validate_parent(self, parent: Category | None) -> Category | None:
        if parent is None:
            return None
        request = self.context.get("request")
        if request is not None and parent.user_id != request.user.id:
            raise serializers.ValidationError("parent must belong to the same user")
        if parent.parent_id is not None:
            raise serializers.ValidationError(
                "categories support only one level of nesting (parent must be a root)"
            )
        return parent

    def validate(self, attrs: dict) -> dict:
        instance: Category | None = self.instance  # type: ignore[assignment]
        if instance is not None and "parent" in attrs:
            new_parent = attrs["parent"]
            if new_parent is not None and new_parent.id == instance.id:
                raise serializers.ValidationError({"parent": "category cannot be its own parent"})
        return attrs


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class TransactionSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True, required=False)
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

    def get_running_balance(self, obj: Transaction) -> str | None:
        balances = self.context.get("running_balances") or {}
        if obj.id not in balances:
            return None
        opening = obj.account.opening_balance if obj.account_id else 0
        return str(balances[obj.id] + opening)

    def validate_account(self, account):
        request = self.context.get("request")
        if request is not None and account.user_id != request.user.id:
            raise serializers.ValidationError("account must belong to the requesting user")
        return account

    def validate_category(self, category):
        if category is None:
            return None
        request = self.context.get("request")
        if request is not None and category.user_id != request.user.id:
            raise serializers.ValidationError("category must belong to the requesting user")
        return category
