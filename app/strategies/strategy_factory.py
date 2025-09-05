from strategies.novichok_strategy import NovichokStrategy
from strategies.compensation_strategy import CompensationStrategy
from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters
from strategies.novichok_adapter import NovichokAdapter
from strategies.compensation_adapter import CompensationAdapter


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
    
    # Безопасно извлекаем параметры из template
    if hasattr(template, 'parameters') and template.parameters:
        parameters = template.parameters

        # Если это уже словарь - используем как есть
        if isinstance(parameters, dict):
            params = parameters
        # Если это SimpleNamespace или другой объект с __dict__
        elif hasattr(parameters, '__dict__'):
            params = parameters.__dict__
        # Если это строка (JSON) - пытаемся распарсить
        elif isinstance(parameters, str):
            try:
                import json
                params = json.loads(parameters)
            except (json.JSONDecodeError, TypeError):
                params = {}
        # Если это итерируемый объект (но не строка)
        elif hasattr(parameters, '__iter__') and not isinstance(parameters, str):
            try:
                params = dict(parameters)
            except (ValueError, TypeError):
                params = {}
        else:
            params = {}
    else:
        params = {}
    
    if name == "novichok":
        # Используем уже подготовленные params
        print(f"🧠 Создание NovichokStrategy с параметрами: {params}")
        legacy = NovichokStrategy(StrategyParameters(raw=params))
        return NovichokAdapter(legacy)
    elif name == "compensation":
        # Используем уже подготовленные params
        print(f"🧠 Создание CompensationStrategy с параметрами: {params}")
        legacy = CompensationStrategy(StrategyParameters(raw=params))
        adapter = CompensationAdapter(legacy, None)  # deal_service = None для бэктеста
        return adapter
    else:
        # Ошибка для неизвестных стратегий
        raise ValueError(f"Strategy '{name}' not found")