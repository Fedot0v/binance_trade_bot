from uuid import UUID
from typing import Optional
from datetime import datetime

from pydantic import BaseModel



class DealBase(BaseModel):
    symbol: str
    side: str
    entry_price: float
    size: float
    status: str
    pnl: Optional[float] = None
    user_id: UUID


class DealCreate(DealBase):
    order_id: Optional[str] = None
    stop_loss_order_id: Optional[str] = None
    stop_loss: Optional[float] = None
    template_id: int
    bot_id: int


class DealRead(DealBase):
    id: int
    order_id: Optional[str] = None
    stop_loss_order_id: Optional[str] = None
    opened_at: datetime
    closed_at: Optional[datetime]
    pnl: Optional[float]
    exit_price: Optional[float] = None

    model_config = {
        "from_attributes": True
    }


class DealDelete(BaseModel):
    id: int
    message: str
