from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DealBase(BaseModel):
    symbol: str
    side: str
    entry_price: float
    size: float
    status: str


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    status: Optional[str] = None
    closed_at: Optional[datetime] = None


class DealRead(DealBase):
    id: int
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }
