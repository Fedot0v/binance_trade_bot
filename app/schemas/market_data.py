from pydantic import BaseModel
from datetime import datetime


class MarketDataBase(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataCreate(MarketDataBase):
    pass


class MarketDataRead(MarketDataBase):
    id: int

    model_config = {
        "from_attributes": True
    }
