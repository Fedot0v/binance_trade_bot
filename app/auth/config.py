from fastapi_users.authentication import (
    JWTStrategy,
    AuthenticationBackend,
    CookieTransport
)


SECRET = "VERY_SECRET"


cookie_transport = CookieTransport(
    cookie_name="binauth",
    cookie_max_age=3600*24*30,
    cookie_secure=True,
    cookie_samesite="lax",
    cookie_domain="binabot.xyz"
    )


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600*24*30)


jwt_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
