import pytest
from unittest.mock import MagicMock

from strategies.strategy_factory import make_strategy
from strategies.registry import REGISTRY


def test_registry_contains_expected_keys():
    assert "novichok" in REGISTRY
    assert "compensation" in REGISTRY
    assert REGISTRY["novichok"]["is_active"] is True
    assert REGISTRY["compensation"]["is_active"] is True


def test_make_strategy_novichok_adapter_created():
    template = MagicMock(symbol="BTCUSDT", parameters={
        "ema_fast": 10,
        "ema_slow": 30,
        "trend_threshold": 0.001,
        "deposit_prct": 0.05,
    })
    strat = make_strategy("novichok", template)
    # Должен быть адаптер с методом decide и required_symbols
    assert hasattr(strat, "decide")
    assert hasattr(strat, "required_symbols")
    assert strat.id == "novichok-adapter"


def test_make_strategy_compensation_adapter_created():
    template = MagicMock(
        interval="1m",
        parameters={
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.001,
            "btc_deposit_prct": 0.05,
            "eth_deposit_prct": 0.1,
        },
    )
    strat = make_strategy("compensation", template)
    assert hasattr(strat, "decide")
    assert hasattr(strat, "required_symbols")
    assert strat.id == "compensation-adapter"


