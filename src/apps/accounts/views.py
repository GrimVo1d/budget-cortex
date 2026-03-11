from __future__ import annotations

from rest_framework import generics, permissions

from .serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    """Open registration endpoint — no auth required."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
