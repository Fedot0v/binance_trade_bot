from app.strategies.novichok_strategy import NovichokStrategy
from app.strategies.base_strategy import BaseStrategy


STRATEGY_REGISTRY = {
    "novichok": NovichokStrategy
}


def get_strategy_class_by_name(name: str) -> BaseStrategy:
    strategy = STRATEGY_REGISTRY.get(name)
    if not strategy:
        raise ValueError(f"Strategy '{name}' not found")
    return strategy
