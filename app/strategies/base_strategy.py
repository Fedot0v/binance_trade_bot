from abc import ABCMeta, abstractmethod
from pandas import DataFrame


class BaseStrategy(ABCMeta):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def generate_signal(self, df: DataFrame) -> str:
        pass

    @abstractmethod
    def calculate_position_size(self, balance: float) -> float:
        pass
