from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StrategyLogBase(BaseModel):
    strategy: str
    signal: str
    comment: Optional[str] = None
    deal_id: Optional[int] = None


class StrategyLogCreate(StrategyLogBase):
    pass


class StrategyLogRead(StrategyLogBase):
    id: int
    timestamp: datetime

    model_config = {
        "from_attributes": True
    }
