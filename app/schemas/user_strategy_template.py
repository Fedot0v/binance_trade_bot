from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import BaseModel


class Symbols(str, Enum):
    BTCUSDT = "BTCUSDT"
    ETHUSDT = "ETHUSDT"
    BNBUSDT = "BNBUSDT"


class Intervals(str, Enum):
    min1 = "1m"
    min5 = "5m"
    min15 = "15m"
    hour1 = "1h"
    hour4 = "4h"
    day1 = "1d"


class UserStrategyTemplateBase(BaseModel):
    template_name: str
    description: Optional[str] = None
    leverage: float
    strategy_config_id: int
    parameters: Optional[dict] = None
    symbol: Symbols
    interval: Intervals


class UserStrategyTemplateCreate(UserStrategyTemplateBase):
    pass


class UserStrategyTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    description: Optional[str] = None
    leverage: Optional[float] = None
    strategy_config_id: Optional[int] = None
    parameters: Optional[dict] = None
    symbol: Symbols
    interval: Intervals


class UserStrategyTemplateRead(UserStrategyTemplateBase):
    id: int
    initial_balance: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    user_id: UUID

    model_config = {
        "from_attributes": True
    }
