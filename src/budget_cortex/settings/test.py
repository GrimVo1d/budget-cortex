"""Test settings: in-memory SQLite by default, PostgreSQL when
``TEST_DATABASE_URL`` is set (``make test-pg``)."""

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, SIMPLE_JWT, env

DEBUG = False
SECRET_KEY = "test-insecure-secret-key"  # noqa: S105
JWT_SIGNING_KEY = "test-insecure-jwt-signing-key-0123456789"
SIMPLE_JWT["SIGNING_KEY"] = JWT_SIGNING_KEY
ALLOWED_HOSTS = ["testserver"]

DATABASES = {
    "default": env.db("TEST_DATABASE_URL", default="sqlite://:memory:"),
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Throttling is exercised by a dedicated test that re-enables it.
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []

LOGGING_CONFIG = None
LOGGING = {}
