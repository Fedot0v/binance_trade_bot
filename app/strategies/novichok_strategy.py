import pandas as pd

from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters


# class NovichokStrategy(BaseStrategy):
#     ema_fast = Param(10, int, "Период быстрой EMA")
#     ema_slow = Param(30, int, "Период медленной EMA")
#     trend_threshold = Param(
#         0.002,
#         float,
#         "Порог фильтра тренда (например, 0.2%)"
#     )
#     risk_pct = Param(0.05, float, "Процент от депозита на сделку")
#     stop_loss_pct = Param(0.009, float, "Процент стоп-лосса (например, 0.9%)")

#     def generate_signal(self, df: DataFrame) -> str:
#         ema_fast_series = df['close'].ewm(span=self.config['ema_fast']).mean()
#         ema_slow_series = df['close'].ewm(span=self.config['ema_slow']).mean()

#         current_ema_fast = ema_fast_series.iloc[-1]
#         current_ema_slow = ema_slow_series.iloc[-1]

#         diff_ratio = (
#             abs(current_ema_fast - current_ema_slow) / current_ema_slow
#         )

#         if diff_ratio < self.config['trend_threshold']:
#             return 'hold'

#         if current_ema_fast > current_ema_slow:
#             return 'long'

#         elif current_ema_fast < current_ema_slow:
#             return 'short'

#         return 'hold'

#     def calculate_position_size(self, balance: float) -> float:
#         return balance * self.config['risk_pct']
class NovichokStrategy(BaseStrategy):
    def __init__(self, params: StrategyParameters):
        self.params = params

        self.ema_fast = self.params.get_int("ema_fast", 10)
        self.ema_slow = self.params.get_int("ema_slow", 30)
        self.trend_threshold = self.params.get_float("trend_threshold", 0.001)
        self.risk_pct = self.params.get_float("deposit_prct", 5.0)

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
        return balance * self.risk_pct / 100
