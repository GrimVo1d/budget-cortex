"""settings.prod must refuse to boot with missing or placeholder secrets."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

GOOD_ENV = {
    "SECRET_KEY": "s" * 50,
    "JWT_SIGNING_KEY": "j" * 50,
    "ALLOWED_HOSTS": "api.budget.internal",
    "DATABASE_URL": "postgres://u:p@db.internal:5432/x",
    "REDIS_URL": "redis://:p@redis.internal:6379/0",
    "CELERY_BROKER_URL": "redis://:p@redis.internal:6379/1",
    "CELERY_RESULT_BACKEND": "redis://:p@redis.internal:6379/2",
}


def _boot(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    clean = {k: v for k, v in os.environ.items() if k not in GOOD_ENV}
    clean.update(env, DJANGO_SETTINGS_MODULE="budget_cortex.settings.prod", PYTHONPATH="src")
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        env=clean,
        capture_output=True,
        text=True,
        check=False,
    )


def test_prod_boots_with_real_secrets() -> None:
    assert _boot(GOOD_ENV).returncode == 0


@pytest.mark.parametrize(
    "override",
    [
        {"SECRET_KEY": ""},
        {"SECRET_KEY": "dev-insecure-change-me-but-long-enough-to-pass-len"},
        {"JWT_SIGNING_KEY": "short"},
        {"JWT_SIGNING_KEY": "s" * 50},
        {"ALLOWED_HOSTS": ""},
        {"REDIS_URL": ""},
        {"CELERY_BROKER_URL": ""},
    ],
)
def test_prod_refuses_bad_config(override: dict[str, str]) -> None:
    env = {k: v for k, v in {**GOOD_ENV, **override}.items() if v}
    result = _boot(env)
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
