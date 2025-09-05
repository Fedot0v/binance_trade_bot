from uuid import UUID
from datetime import datetime

from pydantic import BaseModel

from models.user_model import Symbols, Intervals


class UserBotBase(BaseModel):
    user_id: UUID
    template_id: int
    symbol: Symbols
    interval: Intervals


class UserBotCreate(UserBotBase):
    pass


class UserBotRead(UserBotBase):
    id: int
    status: str
    started_at: datetime | None
    stopped_at: datetime | None
    celery_task_id: str | None

    model_config = {
        "from_attributes": True
    }
