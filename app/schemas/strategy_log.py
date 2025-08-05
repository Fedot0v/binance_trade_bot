from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

class StrategyLogCreate(BaseModel):
    deal_id: int
    user_id: UUID
    strategy: str
    signal: str
    comment: str | None = None


class StrategyLogRead(BaseModel):
    id: int
    user_id: UUID
    timestamp: datetime
    strategy: str
    signal: str
    comment: str | None = None
    deal_id: int

    model_config = {
        "from_attributes": True
    }