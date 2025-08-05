from fastapi import APIRouter

from dependencies.user_dependencies import fastapi_users, jwt_backend
from schemas.user import UserRead, UserCreate, UserUpdate


router = APIRouter()


router.include_router(
    fastapi_users.get_auth_router(jwt_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
