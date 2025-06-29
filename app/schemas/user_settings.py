from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserSettingsBase(BaseModel):
    deposit: float
    leverage: float
    entry_pct: float
    strategy_name: str


class UserSettingsCreate(UserSettingsBase):
    pass


class UserSettingsUpdate(BaseModel):
    deposit: Optional[float] = None
    leverage: Optional[float] = None
    entry_pct: Optional[float] = None
    strategy_name: Optional[str] = None


class UserSettingsRead(UserSettingsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
