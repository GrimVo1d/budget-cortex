"""Bind the session-authenticated user (admin) as the audit actor.

DRF/JWT requests are authenticated later, inside the view; see
:class:`apps.core.audit.AuditActorMixin`. Resetting the context var here
also discards whatever the view set, so nothing leaks between requests.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .audit import reset_actor, set_actor


class AuditMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        actor = user.pk if user is not None and user.is_authenticated else None
        token = set_actor(actor)
        try:
            return self.get_response(request)
        finally:
            reset_actor(token)
