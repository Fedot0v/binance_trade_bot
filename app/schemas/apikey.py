from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class APIKeysBase(BaseModel):
    is_active: Optional[bool] = True


class APIKeysCreate(APIKeysBase):
    user_id: UUID
    api_key: str
    api_secret: str


class APIKeysRead(APIKeysBase):
    id: int
    user_id: UUID
    api_key_encrypted: str
    api_secret_encrypted: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
