import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from strategies.novichok_strategy import NovichokStrategy
from schemas.user_strategy_template import UserStrategyTemplateRead
from schemas.deal import DealCreate  # Твоя схема
from pydantic import BaseModel
from services.strategy_parameters import StrategyParameters


class BacktestResult(BaseModel):
    deals: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]
    total_pnl: float
    final_balance: float
    initial_balance: float
    num_deals: int
    profitable_deals: int
    loss_deals: int
    winrate: float


class BacktestService:
    def __init__(self):
        pass

    async def run_backtest(
        self,
        template: UserStrategyTemplateRead,
        candles_csv_path: str,
        initial_balance: float = 1000.0,
    ) -> BacktestResult:
        candles = pd.read_csv(candles_csv_path)
        candles = candles.sort_values('timestamp')

        params = StrategyParameters(template.parameters)
        strategy = NovichokStrategy(params)

        balance = initial_balance
        equity_curve = []
        deals = []

        position = None
        profitable_deals = 0
        loss_deals = 0

        for idx, row in candles.iterrows():
            price = float(row['close'])
            ts = int(row['timestamp'])
            signal = strategy.generate_signal(row)

            # --- Открытие позиции
            if position is None and signal:
                position = {
                    "side": signal,
                    "entry_price": price,
                    "timestamp": ts,
                }
                continue

            if position:
                stop_loss_pct = float(template.parameters.get(
                    'stop_loss_pct',
                    0.009)
                )
                stop_loss_price = (
                    position["entry_price"] * (1 - stop_loss_pct)
                    if position["side"] == "long"
                    else position["entry_price"] * (1 + stop_loss_pct)
                )

                hit_stop = (price <= stop_loss_price) if position["side"] == "long" else (price >= stop_loss_price)

                reverse_signal = (
                    (signal == "short" and position["side"] == "long")
                    or (signal == "long" and position["side"] == "short")
                )

                if hit_stop or reverse_signal:
                    exit_price = stop_loss_price if hit_stop else price
                    pnl = (
                        (exit_price - position["entry_price"]) / position["entry_price"] * 100
                        if position["side"] == "long"
                        else (position["entry_price"] - exit_price) / position["entry_price"] * 100
                    )
                    balance += balance * pnl / 100
                    deals.append({
                        "entry_price": position["entry_price"],
                        "exit_price": exit_price,
                        "side": position["side"],
                        "open_time": datetime.utcfromtimestamp(position["timestamp"]/1000),
                        "close_time": datetime.utcfromtimestamp(ts/1000),
                        "pnl_pct": pnl,
                        "status": "stop" if hit_stop else "reverse",
                    })
                    if pnl > 0:
                        profitable_deals += 1
                    else:
                        loss_deals += 1
                    position = None
            equity_curve.append({"timestamp": ts, "equity": balance})

        winrate = (profitable_deals / (profitable_deals + loss_deals) * 100) if (profitable_deals + loss_deals) else 0

        return BacktestResult(
            deals=deals,
            equity_curve=equity_curve,
            total_pnl=balance - initial_balance,
            final_balance=balance,
            initial_balance=initial_balance,
            num_deals=len(deals),
            profitable_deals=profitable_deals,
            loss_deals=loss_deals,
            winrate=winrate,
        )
