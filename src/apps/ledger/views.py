from __future__ import annotations

from apps.core.mixins import UserScopedModelViewSet

from .models import Category, Tag
from .serializers import CategorySerializer, TagSerializer


class CategoryViewSet(UserScopedModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filterset_fields = ["kind", "parent"]
    ordering_fields = ["name", "created_at"]


class TagViewSet(UserScopedModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    ordering_fields = ["name", "created_at"]
