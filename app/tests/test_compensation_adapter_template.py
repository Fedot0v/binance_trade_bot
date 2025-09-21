import pandas as pd
import pytest
from unittest.mock import MagicMock

from strategies.compensation_strategy import CompensationStrategy
from strategies.compensation_adapter import CompensationAdapter
from services.strategy_parameters import StrategyParameters


def make_trend_df(start: float, step: float, n: int, freq: str = '1min') -> pd.DataFrame:
    dates = pd.date_range(start='2024-01-01', periods=n, freq=freq)
    prices = [start + i * step for i in range(n)]
    # красим свечи по направлению тренда
    opens = [p + (0.2 if step < 0 else -0.2) for p in prices]
    return pd.DataFrame({
        'open': opens,
        'high': [p + abs(step) for p in prices],
        'low': [p - abs(step) for p in prices],
        'close': prices,
        'volume': [1000] * n
    }, index=dates)


def params(extra: dict | None = None) -> StrategyParameters:
    raw = {
        'ema_fast': 5,
        'ema_slow': 20,
        'trend_threshold': 0.001,
        'btc_deposit_prct': 0.05,
        'btc_stop_loss_pct': 0.012,
        'eth_deposit_prct': 0.1,
        'eth_stop_loss_pct': 0.01,
        'compensation_threshold': 0.002,
        'compensation_delay_candles': 1,
        'impulse_threshold': 0.004,
        'candles_against_threshold': 2,
        'eth_confirmation_candles': 1,
        'require_eth_ema_alignment': True,
        'eth_volume_min_ratio': 0.0,
        'high_adverse_threshold': 0.01,
        'max_compensation_window_candles': 30,
        'eth_compensation_opposite': True,
        'interval': '1m',
    }
    if extra:
        raw.update(extra)
    return StrategyParameters(raw=raw)


@pytest.mark.asyncio
async def test_adapter_creates_eth_compensation_intent_opposite():
    template = MagicMock(interval="1m", parameters={})
    strategy = CompensationStrategy(params())
    adapter = CompensationAdapter(strategy, template, deal_service=None)

    btc_df = make_trend_df(100, -0.5, 60)  # падение против BUY
    eth_df = make_trend_df(2000, -1.0, 60)  # opposite подтверждает SELL

    # Открыта позиция BTC BUY, ETH нет
    open_state = {
        "BTCUSDT": {
            "position": {
                "side": "BUY",
                "entry_price": 100.0,
                "entry_time": btc_df.index[-20],
            }
        }
    }

    # Считаем, что сигнал был замечен пару свечей назад
    strategy.update_state(
        btc_deal_id=1,
        btc_entry_price=100.0,
        btc_entry_time=btc_df.index[-20],
        btc_side="BUY",
    )
    strategy.state.compensation_signal_time = btc_df.index[-3]

    md = {"BTCUSDT": btc_df, "ETHUSDT": eth_df}
    decision = await adapter.decide(md, template, open_state)

    intents = decision.intents
    assert any(i.symbol == "ETHUSDT" and i.side == "SELL" and i.role == "compensation" for i in intents)


@pytest.mark.asyncio
async def test_adapter_emergency_close_eth_without_btc():
    template = MagicMock(interval="1m", parameters={})
    strategy = CompensationStrategy(params())
    adapter = CompensationAdapter(strategy, template, deal_service=None)

    # ETH позиция есть, BTC нет — должен создаться emergency_close для ETH
    btc_df = make_trend_df(100, 0.1, 10)
    eth_df = make_trend_df(2000, 0.1, 10)

    open_state = {
        "ETHUSDT": {
            "position": {
                "side": "BUY",
                "entry_price": 2000.0,
                "entry_time": eth_df.index[-5],
            }
        }
    }

    decision = await adapter.decide({"BTCUSDT": btc_df, "ETHUSDT": eth_df}, template, open_state)
    intents = decision.intents
    assert any(i.symbol == "ETHUSDT" and i.role == "emergency_close" for i in intents)


