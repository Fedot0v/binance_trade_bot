from typing import List

from pydantic import BaseModel


class DealResult(BaseModel):
    entry_time: int
    entry: float
    exit: float
    pnl: float


class BacktestResult(BaseModel):
    deals: List[DealResult]
    equity: list
    stats: dict