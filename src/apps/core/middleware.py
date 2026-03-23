"""Per-request middleware: bind the authenticated user to a thread-local
so audit-log signal handlers can attribute writes without plumbing the
user kwarg through every service.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .audit import clear_actor, set_actor


class AuditMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            set_actor(user.id)
        try:
            return self.get_response(request)
        finally:
            clear_actor()
