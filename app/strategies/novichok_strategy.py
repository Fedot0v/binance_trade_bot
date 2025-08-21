import pandas as pd

from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters


class NovichokStrategy(BaseStrategy):
    def __init__(self, params: StrategyParameters):
        self.params = params

        self.ema_fast = self.params.get_int("ema_fast", 10)
        self.ema_slow = self.params.get_int("ema_slow", 30)
        self.trend_threshold = self.params.get_float("trend_threshold", 0.001)
        self.risk_pct = self.params.get_float("deposit_prct", 0.05)
        self.stop_loss_pct = self.params.get_float("stop_loss_pct", 0.02)

    def generate_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.ema_slow:
            return 'hold'

        ema_fast = df['close'].ewm(span=self.ema_fast).mean()
        ema_slow = df['close'].ewm(span=self.ema_slow).mean()

        diff = abs(ema_fast.iloc[-1] - ema_slow.iloc[-1]) / ema_slow.iloc[-1]
        if diff < self.trend_threshold:
            return 'hold'

        return 'long' if ema_fast.iloc[-1] > ema_slow.iloc[-1] else 'short'

    def calculate_position_size(self, balance: float) -> float:
        return balance * self.risk_pct
    
    def calculate_stop_loss_price(self, entry_price: float, side: str) -> float:
        """Рассчитывает цену стоп-лосса на основе процента"""
        if side == "BUY":
            return entry_price * (1 - self.stop_loss_pct)
        else:  # SELL
            return entry_price * (1 + self.stop_loss_pct)
