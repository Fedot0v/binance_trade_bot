from abc import ABC, abstractmethod
from pandas import DataFrame


class BaseStrategy(ABC):
    """
    Абстрактный базовый класс для торговых шаблонов стратегий.
    Каждый шаблон стратегии должен реализовать эти методы.
    """

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def generate_signal(self, df: DataFrame) -> str:
        """
        На вход подаётся датафрейм со свечами.
        Метод должен вернуть сигнал: 'long', 'short' или 'hold'.
        """
        pass

    @abstractmethod
    def calculate_position_size(self, balance: float) -> float:
        """
        Возвращает размер позиции в USDT на основе текущего баланса.
        """
        pass
