from strategies.novichok_strategy import NovichokStrategy
from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters
from strategies.novichok_adapter import NovichokAdapter


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


def make_strategy(strategy_name: str, template) -> object:
    """
    Возвращает объект-стратегию по единому контракту (required_symbols/decide).
    Для novichok — вернёт NovichokAdapter(NovichokStrategy(...)).
    """
    name = (strategy_name or "novichok").lower()
    if name == "novichok":
        legacy = NovichokStrategy(StrategyParameters(getattr(template, "parameters", {}) or {}))
        return NovichokAdapter(legacy)
    # тут позже добавишь elif name == "controlled": return ControlledEntryStrategy(...)
    legacy = NovichokStrategy(StrategyParameters(getattr(template, "parameters", {}) or {}))
    return NovichokAdapter(legacy)