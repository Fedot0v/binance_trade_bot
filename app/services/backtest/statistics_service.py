from __future__ import annotations

from typing import List, Dict, Any
from math import sqrt


class BacktestStatisticsService:
    """Сервис расчёта ключевых метрик бектеста."""

    def calculate_statistics(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: List[Any],
        initial_balance: float
    ) -> Dict[str, float]:
        if not equity_curve:
            return self._empty_stats()

        final_balance = equity_curve[-1].balance if hasattr(equity_curve[-1], 'balance') else equity_curve[-1]['balance']
        total_pnl = final_balance - initial_balance
        total_pnl_pct = (final_balance / initial_balance - 1.0) if initial_balance else 0.0

        # Win/Loss
        wins = 0
        losses = 0
        win_amounts: List[float] = []
        loss_amounts: List[float] = []
        for t in trades:
            pnl = t.get('pnl', 0.0)
            if pnl > 0:
                wins += 1
                win_amounts.append(pnl)
            elif pnl < 0:
                losses += 1
                loss_amounts.append(abs(pnl))

        total_trades = len(trades)
        win_rate = (wins / total_trades * 100.0) if total_trades else 0.0

        avg_win = (sum(win_amounts) / len(win_amounts)) if win_amounts else 0.0
        avg_loss = (sum(loss_amounts) / len(loss_amounts)) if loss_amounts else 0.0

        profit_factor = (sum(win_amounts) / sum(loss_amounts)) if loss_amounts else (sum(win_amounts) if win_amounts else 0.0)

        # Max drawdown
        max_dd, max_dd_pct = self._calculate_max_drawdown(equity_curve)

        # Sharpe
        sharpe = self._calculate_sharpe(equity_curve)

        return {
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'winning_trades': wins,
            'losing_trades': losses,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
        }

    def _calculate_max_drawdown(self, equity_curve: List[Any]) -> tuple[float, float]:
        peak = None
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        for pt in equity_curve:
            bal = pt.balance if hasattr(pt, 'balance') else pt['balance']
            if peak is None or bal > peak:
                peak = bal
            if peak and bal < peak:
                dd = peak - bal
                dd_pct = dd / peak
                if dd > max_drawdown:
                    max_drawdown = dd
                if dd_pct > max_drawdown_pct:
                    max_drawdown_pct = dd_pct
        return max_drawdown, max_drawdown_pct

    def _calculate_sharpe(self, equity_curve: List[Any]) -> float:
        returns: List[float] = []
        prev = None
        for pt in equity_curve:
            bal = pt.balance if hasattr(pt, 'balance') else pt['balance']
            if prev is not None and prev:
                returns.append((bal - prev) / prev)
            prev = bal

        if not returns:
            return 0.0

        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std = sqrt(variance) if variance > 0 else 0.0
        if std == 0:
            return 0.0
        return mean_r / std

    def _empty_stats(self) -> Dict[str, float]:
        return {
            'total_pnl': 0.0,
            'total_pnl_pct': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_pct': 0.0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
        }


