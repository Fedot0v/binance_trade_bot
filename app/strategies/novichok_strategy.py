import pandas as pd
from typing import Dict

from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters


class NovichokStrategy(BaseStrategy):
    def __init__(self, params: StrategyParameters):
        # Используем параметры напрямую без конвертации
        # Все процентные параметры хранятся как числа (не проценты)

        # Создаем конфиг для BaseStrategy
        config = {
            'stop_loss_pct': params.get_float("stop_loss_pct", 0.02),
            'trailing_stop_pct': params.get_float("trailing_stop_pct", 0.005),
            'trailing_stop_enabled': params.get_bool("trailing_stop_enabled", True),
            'trailing_stop_update_on_tick': params.get_bool("trailing_stop_update_on_tick", True)
        }
        super().__init__(config)

        self.params = params

        # Параметры стратегии (все в долях/числах, не процентах)
        self.ema_fast = self.params.get_int("ema_fast", 10)
        self.ema_slow = self.params.get_int("ema_slow", 30)
        self.trend_threshold = self.params.get_float("trend_threshold", 0.001)  # доли
        self.risk_pct = self.params.get_float("deposit_prct", 0.05)  # доли
        self.stop_loss_pct = self.params.get_float("stop_loss_pct", 0.02)  # доли
        self.take_profit_pct = self.params.get_float("take_profit_pct", 0.03)  # доли
        self.trailing_stop_pct = self.params.get_float("trailing_stop_pct", 0.005)  # доли

    def generate_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.ema_slow:
            return None

        ema_fast = df['close'].ewm(span=self.ema_fast).mean()
        ema_slow = df['close'].ewm(span=self.ema_slow).mean()

        diff = abs(ema_fast.iloc[-1] - ema_slow.iloc[-1]) / ema_slow.iloc[-1]
        if diff < self.trend_threshold:
            return None

        # Возвращаем сигнал входа (long/short)
        return 'long' if ema_fast.iloc[-1] > ema_slow.iloc[-1] else 'short'

    def calculate_position_size(self, balance: float) -> float:
        return balance * self.risk_pct
    
    def calculate_stop_loss_price(self, entry_price: float, side: str, symbol: str) -> float:
        """Рассчитывает цену стоп-лосса на основе процента"""
        if side == "long":
            return entry_price * (1 - self.stop_loss_pct)
        else:  # short
            return entry_price * (1 + self.stop_loss_pct)

    def calculate_take_profit_price(self, entry_price: float, side: str, symbol: str) -> float:
        """Рассчитывает цену тейк-профи на основе процента"""
        if side == "long":
            return entry_price * (1 + self.take_profit_pct)
        else:  # short
            return entry_price * (1 - self.take_profit_pct)

    def calculate_trailing_stop_price(self, entry_price: float, current_price: float, side: str, symbol: str) -> float:
        """Рассчитывает цену трейлинг-стопа (упрощенная версия)"""
        if side == "long":
            # Для лонга: стоп-лосс на trailing_stop_pct ниже текущей цены
            return current_price * (1 - self.trailing_stop_pct)
        else:  # short
            # Для шорта: стоп-лосс на trailing_stop_pct выше текущей цены
            return current_price * (1 + self.trailing_stop_pct)
    
    def should_close_position(self, deal, market_data: Dict[str, pd.DataFrame]) -> bool:
        """Определяет, нужно ли закрыть позицию по стратегии"""
        # Для Novichok стратегии - НЕ закрываем позицию по сигналу!
        # Выход происходит ТОЛЬКО по стоп-лоссу (trailing stop)
        # Логика стоп-лосса реализована в BaseStrategy
        return False
