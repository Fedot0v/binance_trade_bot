from typing import Any, Dict, Optional

from pydantic import BaseModel


class StrategyConfigBase(BaseModel):
    name: str
    is_active: Optional[bool] = True
    description: str = ""
    parameters: Dict[str, Any]


class StrategyConfigCreate(StrategyConfigBase):
    pass


class StrategyConfigUpdate(BaseModel):
    is_active: Optional[bool] = None
    parameters: Optional[Dict[str, Any]] = None
    description: str = ""


class StrategyConfigRead(StrategyConfigBase):
    id: int

    model_config = {
        "from_attributes": True
    }
