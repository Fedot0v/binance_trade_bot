import uuid

from fastapi_users import FastAPIUsers

from models.user_model import User
from auth.user_manager import get_user_manager
from auth.config import jwt_backend


fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [jwt_backend],
)
