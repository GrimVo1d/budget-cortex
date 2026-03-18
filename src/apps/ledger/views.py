from __future__ import annotations

from apps.core.mixins import UserScopedModelViewSet

from .filters import TransactionFilter
from .models import Category, Tag, Transaction
from .serializers import CategorySerializer, TagSerializer, TransactionSerializer


class CategoryViewSet(UserScopedModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filterset_fields = ["kind", "parent"]
    ordering_fields = ["name", "created_at"]


class TagViewSet(UserScopedModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    ordering_fields = ["name", "created_at"]


class TransactionViewSet(UserScopedModelViewSet):
    queryset = Transaction.objects.all().select_related("account", "category")
    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter
    ordering_fields = ["occurred_at", "amount", "created_at"]
