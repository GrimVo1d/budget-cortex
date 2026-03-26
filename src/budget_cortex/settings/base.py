"""Base Django settings shared by dev / test / prod.

All env-driven via django-environ. See `.env.example` for the canonical list
and defaults.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = BASE_DIR / "src"

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, "dev-insecure-change-me"),
    ALLOWED_HOSTS=(list, ["*"]),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    REDIS_URL=(str, "redis://localhost:6379/0"),
    CELERY_BROKER_URL=(str, "redis://localhost:6379/1"),
    CELERY_RESULT_BACKEND=(str, "redis://localhost:6379/2"),
    JWT_SIGNING_KEY=(str, "dev-insecure-jwt"),
    FX_PROVIDER=(str, "stub"),
    FX_BASE_CURRENCY=(str, "RUB"),
    LOG_LEVEL=(str, "INFO"),
    LOG_FORMAT=(str, "plain"),
)

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "apps.core",
    "apps.accounts",
    "apps.ledger",
    "apps.analytics",
    "apps.fx",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.AuditMiddleware",
]

ROOT_URLCONF = "budget_cortex.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "budget_cortex.wsgi.application"
ASGI_APPLICATION = "budget_cortex.asgi.application"

DATABASES = {"default": env.db()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "budget-cortex API",
    "DESCRIPTION": "Personal finance REST service with PostgreSQL analytics.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

JWT_SIGNING_KEY = env("JWT_SIGNING_KEY")
FX_PROVIDER = env("FX_PROVIDER")
FX_BASE_CURRENCY = env("FX_BASE_CURRENCY")

SIMPLE_JWT = {
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

from kombu import Queue  # noqa: E402

CELERY_TASK_QUEUES = (
    Queue("default"),
    Queue("low"),
)
CELERY_TASK_DEFAULT_QUEUE = "default"

CELERY_TASK_ROUTES = {
    "tasks.imports.parse_csv_import": {"queue": "default"},
    "tasks.analytics.refresh_materialized_views": {"queue": "low"},
    "tasks.fx.fetch_fx_rates": {"queue": "low"},
    "tasks.budgets.evaluate_budgets": {"queue": "low"},
    "tasks.imports.cleanup_csv_files": {"queue": "low"},
}

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "refresh-materialized-views": {
        "task": "tasks.analytics.refresh_materialized_views",
        "schedule": crontab(minute="0"),  # every hour
    },
    "fetch-fx-rates": {
        "task": "tasks.fx.fetch_fx_rates",
        "schedule": crontab(hour="6", minute="0"),  # daily 06:00 UTC
    },
    "evaluate-budgets": {
        "task": "tasks.budgets.evaluate_budgets",
        "schedule": crontab(hour="7", minute="0"),  # daily 07:00 UTC
    },
    "cleanup-csv-files": {
        "task": "tasks.imports.cleanup_csv_files",
        "schedule": crontab(hour="3", minute="0", day_of_week="sunday"),
    },
}

LOG_LEVEL = env("LOG_LEVEL")
LOG_FORMAT = env("LOG_FORMAT")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "json": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT if LOG_FORMAT in {"plain", "json"} else "plain",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "celery": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
