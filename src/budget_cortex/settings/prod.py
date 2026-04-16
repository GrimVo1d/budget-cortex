"""Production: every secret and host must come from the environment."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import LOGGING, SIMPLE_JWT, SPECTACULAR_SETTINGS, env

DEBUG = False

_MIN_KEY_LENGTH = 32


def _require_secret(name: str) -> str:
    value = str(env.str(name, default=""))
    if len(value) < _MIN_KEY_LENGTH or value.startswith("dev-insecure"):
        raise ImproperlyConfigured(
            f"{name} must be set to a random value of at least {_MIN_KEY_LENGTH} characters"
        )
    return value


SECRET_KEY = _require_secret("SECRET_KEY")
JWT_SIGNING_KEY = _require_secret("JWT_SIGNING_KEY")
if JWT_SIGNING_KEY == SECRET_KEY:
    raise ImproperlyConfigured("JWT_SIGNING_KEY must differ from SECRET_KEY")
SIMPLE_JWT["SIGNING_KEY"] = JWT_SIGNING_KEY

# No silent fallbacks: missing values raise ImproperlyConfigured.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
DATABASES = {"default": env.db("DATABASE_URL")}
REDIS_URL = env.str("REDIS_URL")
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
}
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND")

# The schema and Swagger UI are for staff only in production.
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^health/"]
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31_536_000)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

LOGGING["handlers"]["console"]["formatter"] = "json"  # type: ignore[index]
