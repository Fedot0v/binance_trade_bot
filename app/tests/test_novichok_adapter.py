import pandas as pd
import pytest
from unittest.mock import MagicMock

from strategies.novichok_strategy import NovichokStrategy
from strategies.novichok_adapter import NovichokAdapter
from services.strategy_parameters import StrategyParameters


def make_trend_df(start: float, step: float, n: int, freq: str = '1min') -> pd.DataFrame:
    dates = pd.date_range(start='2024-01-01', periods=n, freq=freq)
    prices = [start + i * step for i in range(n)]
    return pd.DataFrame({
        'open': prices,
        'high': [p * 1.001 for p in prices],
        'low': [p * 0.999 for p in prices],
        'close': prices,
        'volume': [100] * n
    }, index=dates)


def make_legacy(params: dict | None = None) -> NovichokStrategy:
    p = StrategyParameters(raw=params or {
        'ema_fast': 5,
        'ema_slow': 10,
        'trend_threshold': 0.0001,
        'deposit_prct': 0.05,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.03,
        'trailing_stop_pct': 0.005,
    })
    return NovichokStrategy(p)


@pytest.mark.asyncio
async def test_required_symbols_and_primary_intent_created_buy():
    legacy = make_legacy()
    adapter = NovichokAdapter(legacy)

    template = MagicMock(symbol="BTCUSDT", deposit_prct=0.07)
    assert adapter.required_symbols(template) == ["BTCUSDT"]

    # Восходящий тренд → сигнал long → BUY intent
    df = make_trend_df(100, 1.0, 50)
    decision = await adapter.decide({"BTCUSDT": df}, template, open_state=None)

    assert len(decision.intents) == 1
    i = decision.intents[0]
    assert i.symbol == "BTCUSDT"
    assert i.side == "BUY"
    assert i.role == "primary"
    # размер берётся из template.deposit_prct
    assert i.size == pytest.approx(0.07, rel=1e-6)


@pytest.mark.asyncio
async def test_no_intents_when_no_data():
    legacy = make_legacy()
    adapter = NovichokAdapter(legacy)
    template = MagicMock(symbol="BTCUSDT", deposit_prct=0.05)

    decision = await adapter.decide({}, template, open_state=None)
    assert decision.intents == []


