"""Local development: throwaway secrets, DEBUG on, any host."""

from .base import *  # noqa: F403
from .base import SIMPLE_JWT, env

DEBUG = env.bool("DEBUG", default=True)
# Not "*": with DEBUG on that would invite DNS rebinding against the local stack.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])

SECRET_KEY = env.str("SECRET_KEY", default="dev-insecure-change-me")
JWT_SIGNING_KEY = env.str("JWT_SIGNING_KEY", default="dev-insecure-jwt-signing-key-change-me")
SIMPLE_JWT["SIGNING_KEY"] = JWT_SIGNING_KEY
