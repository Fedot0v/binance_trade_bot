import os

from fastapi_users.authentication import (
    JWTStrategy,
    AuthenticationBackend,
    CookieTransport
)


SECRET = os.environ.get("SECRET")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "local")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"


# Настройки для разных окружений
if ENVIRONMENT == "production":
    cookie_secure = True
    cookie_domain = "binabot.xyz"
else:
    cookie_secure = False
    cookie_domain = None  # Для локальной разработки


cookie_transport = CookieTransport(
    cookie_name="binauth",
    cookie_max_age=3600*24*30,
    cookie_secure=cookie_secure,
    cookie_samesite="lax",
    cookie_domain=cookie_domain
    )


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600*24*30)


jwt_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
