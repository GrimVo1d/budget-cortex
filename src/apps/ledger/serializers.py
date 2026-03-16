from __future__ import annotations

from rest_framework import serializers

from .models import Category, Tag


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
