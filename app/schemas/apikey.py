from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class APIKeysBase(BaseModel):
    is_active: Optional[bool] = True


class APIKeysCreate(APIKeysBase):
    user_id: int          # <--- Добавить user_id
    api_key: str
    api_secret: str


class APIKeysRead(APIKeysBase):
    id: int
    user_id: int          # <--- Добавить user_id
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
