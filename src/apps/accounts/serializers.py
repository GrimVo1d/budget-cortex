from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Account

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": True},
        }

    def create(self, validated_data: dict):  # type: ignore[override]
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        return user


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            "id",
            "name",
            "type",
            "currency",
            "opening_balance",
            "is_archived",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
