import uuid

from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi import Depends

from models.user_model import User
from dependencies.db_dependencie import get_user_db


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = "SECRET"
    verification_token_secret = "SECRET"

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} зарегистрирован.")


async def get_user_manager(user_db: UserManager = Depends(get_user_db)):
    yield UserManager(user_db)
