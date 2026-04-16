from __future__ import annotations

from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request


def user_id(request: Request) -> int:
    """Primary key of the authenticated user (views require authentication)."""
    pk = request.user.pk
    if pk is None:
        raise NotAuthenticated
    return int(pk)
