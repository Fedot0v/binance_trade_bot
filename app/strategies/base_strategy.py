from abc import ABC, abstractmethod

from pandas import DataFrame
from typing import Optional, Dict, Any

# Константы для процентных параметров стратегий
PERCENTAGE_PARAMS = [
    'stop_loss_pct', 'take_profit_pct', 'trailing_stop_pct',
    'trend_threshold', 'risk_pct', 'deposit_prct'
]


def format_params_for_display(params_dict):
    """
    Универсальная функция для форматирования параметров стратегии для отображения.
    Конвертирует доли в проценты для процентных параметров.

    Args:
        params_dict: Словарь с параметрами стратегии

    Returns:
        Словарь с отформатированными параметрами для отображения
    """
    if not isinstance(params_dict, dict):
        return params_dict

    # Список параметров, которые отображаются в процентах
    percentage_display_params = [
        'stop_loss_pct', 'take_profit_pct', 'trailing_stop_pct',
        'trend_threshold', 'risk_pct', 'deposit_prct'
    ]

    formatted = {}
    for key, value in params_dict.items():
        if key in percentage_display_params and isinstance(value, (int, float)):
            # Конвертируем доли в проценты для отображения
            if value < 1:  # Если значение < 1, значит это доли
                formatted[key] = f"{value * 100:.1f}%"
            else:  # Если значение >= 1, значит уже в процентах
                formatted[key] = f"{value:.1f}%"
        else:
            # Оставляем как есть для остальных параметров
            formatted[key] = value

    return formatted


def should_show_percentage_format(params_dict):
    """
    Определяет, следует ли показывать параметры в процентном формате.
    Возвращает True если стратегия содержит процентные параметры.

    Args:
        params_dict: Словарь с параметрами стратегии

    Returns:
        bool: True если нужно показывать в процентах
    """
    if not isinstance(params_dict, dict):
        return False

    return any(key in params_dict for key in PERCENTAGE_PARAMS)


# PercentageConversionMixin удален - конвертация теперь происходит на фронтенде


class BaseStrategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def generate_signal(self, df: DataFrame) -> str:
        """Генерирует торговый сигнал: 'long', 'short' или None"""
        pass

    @abstractmethod
    def calculate_position_size(self, balance: float) -> float:
        """Рассчитывает размер позиции в долларах"""
        pass
    
    def calculate_stop_loss_price(self, entry_price: float, side: str, symbol: str) -> Optional[float]:
        """Рассчитывает цену стоп-лосса (опционально)"""
        if 'stop_loss_pct' in self.config:
            stop_loss_pct = self.config['stop_loss_pct']
            if side == 'long':
                return entry_price * (1 - stop_loss_pct)
            else:
                return entry_price * (1 + stop_loss_pct)
        return None
    
    def calculate_take_profit_price(self, entry_price: float, side: str, symbol: str) -> Optional[float]:
        """Рассчитывает цену тейк-профита (опционально)"""
        if 'take_profit_pct' in self.config:
            take_profit_pct = self.config['take_profit_pct']
            if side == 'long':
                return entry_price * (1 + take_profit_pct)
            else:
                return entry_price * (1 - take_profit_pct)
        return None
    
    def should_update_trailing_stop(self, deal, current_price: float) -> bool:
        """Определяет, нужно ли обновлять trailing stop"""
        if not hasattr(deal, 'max_price') or not hasattr(deal, 'min_price'):
            return False
            
        if deal.side == 'BUY':
            return current_price > getattr(deal, 'max_price', deal.entry_price)
        else:
            return current_price < getattr(deal, 'min_price', deal.entry_price)
    
    def calculate_trailing_stop_price(self, deal, current_price: float) -> Optional[float]:
        """Рассчитывает новую цену trailing stop"""
        if not self.should_update_trailing_stop(deal, current_price):
            return None

        # Получаем процент trailing stop из конфига или используем дефолтный
        trailing_pct = self.config.get('trailing_stop_pct', 0.002)

        if deal.side == 'BUY':
            return current_price * (1 - trailing_pct)
        else:
            return current_price * (1 + trailing_pct)

    def calculate_trailing_stop_price_legacy(self, entry_price: float, current_price: float, side: str, symbol: str) -> Optional[float]:
        """Устаревший метод для совместимости с бэктестом - НЕ ИСПОЛЬЗОВАТЬ в новой коде"""
        # Этот метод игнорирует логику should_update_trailing_stop!
        # Он просто рассчитывает trailing stop без проверки условий обновления

        trailing_pct = self.config.get('trailing_stop_pct', 0.002)

        if side == 'long':
            return current_price * (1 - trailing_pct)
        else:  # short
            return current_price * (1 + trailing_pct)
    
    def should_close_position(self, deal, market_data: Dict[str, DataFrame]) -> bool:
        """Определяет, нужно ли закрыть позицию"""
        # Базовая реализация - всегда False, переопределяется в наследниках
        return False
    
    def get_trailing_stop_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию trailing stop"""
        return {
            'enabled': self.config.get('trailing_stop_enabled', True),
            'percentage': self.config.get('trailing_stop_pct', 0.002),
            'update_on_tick': self.config.get('trailing_stop_update_on_tick', True)
        }
