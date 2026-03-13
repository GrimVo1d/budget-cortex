from __future__ import annotations

from rest_framework import generics, permissions

from apps.core.mixins import UserScopedModelViewSet

from .models import Account
from .serializers import AccountSerializer, RegisterSerializer


class RegisterView(generics.CreateAPIView):
    """Open registration endpoint — no auth required."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class AccountViewSet(UserScopedModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    filterset_fields = ["type", "currency", "is_archived"]
    ordering_fields = ["name", "created_at"]
