from __future__ import annotations

from typing import Dict, Any, List
from schemas.backtest import BacktestResult


class ResultBuilder:
    def __init__(self, stats_service):
        self.stats_service = stats_service

    def build(
        self,
        strategy_name: str,
        symbol: str,
        start_date,
        end_date,
        initial_balance: float,
        final_balance: float,
        trades: List[Dict[str, Any]],
        equity_curve: List[Any],
        parameters: Dict[str, Any],
        leverage: int = 1,
    ) -> BacktestResult:
        stats = self.stats_service.calculate_statistics(trades, equity_curve, initial_balance)
        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            final_balance=final_balance,
            total_trades=len(trades),
            trades=trades,
            equity_curve=equity_curve,
            parameters=parameters,
            leverage=leverage,
            **stats,
        )


