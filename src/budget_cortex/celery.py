"""Celery application. Task modules are listed in ``CELERY_IMPORTS``."""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budget_cortex.settings.prod")

app = Celery("budget_cortex")
app.config_from_object("django.conf:settings", namespace="CELERY")
