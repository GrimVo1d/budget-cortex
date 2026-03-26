"""Celery application factory."""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budget_cortex.settings.dev")

app = Celery("budget_cortex")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["tasks"])
