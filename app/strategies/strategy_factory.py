from strategies.novichok_strategy import NovichokStrategy
from strategies.compensation_strategy import CompensationStrategy
from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters
from strategies.novichok_adapter import NovichokAdapter
from strategies.compensation_adapter import CompensationAdapter
from services.deal_service import DealService # Импортируем DealService


STRATEGY_REGISTRY = {
    "novichok": NovichokStrategy,
    "compensation": CompensationStrategy
}


def get_strategy_class_by_name(
    name: str,
    params: StrategyParameters
) -> BaseStrategy:
    strategy_cls = STRATEGY_REGISTRY.get(name.lower())
    if not strategy_cls:
        raise ValueError(f"Strategy '{name}' not found")
    return strategy_cls(params)


def make_strategy(strategy_name: str, template) -> object:
    """
    Возвращает объект-стратегию по единому контракту (required_symbols/decide).
    Для novichok — вернёт NovichokAdapter(NovichokStrategy(...)).
    Для compensation — вернёт CompensationAdapter(CompensationStrategy(...)).
    """
    name = (strategy_name or "novichok").lower()
    
    if hasattr(template, 'parameters') and template.parameters:
        parameters = template.parameters

        if isinstance(parameters, dict):
            params = parameters
        elif hasattr(parameters, '__dict__'):
            params = parameters.__dict__
        elif isinstance(parameters, str):
            try:
                import json
                params = json.loads(parameters)
            except (json.JSONDecodeError, TypeError):
                params = {}
        elif hasattr(parameters, '__iter__') and not isinstance(parameters, str):
            try:
                params = dict(parameters)
            except (ValueError, TypeError):
                params = {}
        else:
            params = {}
    else:
        params = {}
    
    # Создаем фиктивный DealService для бэктеста, так как реальный сервис не нужен
    class MockDealService(DealService):
        def __init__(self):
            pass

        async def open_position(self, symbol: str, side: str, amount: float, leverage: int = 1, deal_id: int = None):
            print(f"[MockDealService] Открытие позиции {side} {amount} {symbol}")
            return {"orderId": "mock_order_id", "price": 100.0, "qty": amount}

        async def close_position(self, symbol: str, side: str, deal_id: int):
            print(f"[MockDealService] Закрытие позиции {side} {symbol}")
            return {"orderId": "mock_close_order_id", "price": 100.0, "qty": 0.0}

        async def get_open_positions(self):
            return []
        
        async def get_klines(self, symbol: str, interval: str, limit: int = 500):
            return []

    mock_deal_service = MockDealService()

    if name == "novichok":
        print(f"🧠 Создание NovichokStrategy с параметрами: {params}")
        legacy = NovichokStrategy(StrategyParameters(raw=params))
        return NovichokAdapter(legacy)
    elif name == "compensation":
        print(f"🧠 Создание CompensationStrategy с параметрами: {params}")
        legacy = CompensationStrategy(StrategyParameters(raw={**params, "interval": template.interval}))
        adapter = CompensationAdapter(legacy, template, mock_deal_service)
        return adapter
    else:
        raise ValueError(f"Strategy '{name}' not found")