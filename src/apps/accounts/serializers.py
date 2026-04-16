from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Account

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer[AbstractUser]):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {
            "email": {"required": True, "allow_blank": False},
            "username": {"required": True},
        }

    def validate_email(self, email: str) -> str:
        email = User.objects.normalize_email(email)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("a user with this email already exists")
        return email

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # Validate against a transient user so UserAttributeSimilarityValidator
        # can compare the password with the username and email.
        candidate = User(username=attrs["username"], email=attrs["email"])
        validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data: dict[str, Any]) -> AbstractUser:
        user: AbstractUser = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        return user


class AccountSerializer(serializers.ModelSerializer[Account]):
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

    def validate_currency(self, currency: str) -> str:
        return validate_currency_code(currency)


def validate_currency_code(value: str) -> str:
    code = value.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise serializers.ValidationError("currency must be a 3-letter ISO 4217 code")
    return code
