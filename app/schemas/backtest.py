from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime


class BacktestRequest(BaseModel):
    """Request to run a backtest"""
    template_id: int
    symbol: str = "BTCUSDT"
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
    initial_balance: float = 10000.0
    parameters: Optional[Dict[str, Any]] = None


class BacktestTrade(BaseModel):
    """Trade information in backtest"""
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float
    exit_price: Optional[float] = None
    side: str
    size: float
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    reason: str
    symbol: str
    leverage: int = 1
    status: str = 'unknown'


class BacktestEquityPoint(BaseModel):
    """Point on the equity curve"""
    timestamp: datetime
    balance: float


class BacktestResult(BaseModel):
    """Backtest result"""
    strategy_name: str
    symbol: str
    template_id: int
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_pnl: float
    total_pnl_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    trades: List[BacktestTrade]
    equity_curve: List[BacktestEquityPoint]
    parameters: Dict[str, Any]
    leverage: int = 1  # Leverage used in backtest


class AvailableStrategy(BaseModel):
    """Available strategy template for backtest"""
    key: str
    name: str
    description: str
    default_parameters: Dict[str, Any]
    is_active: bool