from __future__ import annotations

from collections.abc import Sequence

from rest_framework import generics, permissions
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from apps.core.mixins import UserScopedModelViewSet

from .models import Account
from .serializers import AccountSerializer, RegisterSerializer


class AuthThrottleMixin:
    """Tight per-IP rate limit for credential endpoints (scope ``auth``)."""

    throttle_classes: Sequence[type[BaseThrottle]] = [ScopedRateThrottle]
    throttle_scope = "auth"


class RegisterView(AuthThrottleMixin, generics.CreateAPIView):  # type: ignore[type-arg]
    """Open registration endpoint — no auth required."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class TokenView(AuthThrottleMixin, TokenObtainPairView):
    pass


class TokenRefreshThrottledView(AuthThrottleMixin, TokenRefreshView):
    pass


class LogoutView(AuthThrottleMixin, TokenBlacklistView):
    """Blacklist a refresh token so it can no longer be used."""


class AccountViewSet(UserScopedModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    filterset_fields = ["type", "currency", "is_archived"]
    ordering_fields = ["name", "created_at"]
