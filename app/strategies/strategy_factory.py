from strategies.novichok_strategy import NovichokStrategy
from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters


STRATEGY_REGISTRY = {
    "novichok": NovichokStrategy
}


def get_strategy_class_by_name(
    name: str,
    params: StrategyParameters
) -> BaseStrategy:
    strategy_cls = STRATEGY_REGISTRY.get(name.lower())
    if not strategy_cls:
        raise ValueError(f"Strategy '{name}' not found")
    return strategy_cls(params)
