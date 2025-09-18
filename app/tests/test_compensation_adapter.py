import pytest
import pandas as pd
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from strategies.compensation_strategy import CompensationStrategy
from strategies.compensation_adapter import CompensationAdapter
from services.strategy_parameters import StrategyParameters


def make_trend_df(start: float, step: float, n: int, freq: str = '1min') -> pd.DataFrame:
    dates = pd.date_range(start='2024-01-01', periods=n, freq=freq)
    prices = [start + i * step for i in range(n)]
    return pd.DataFrame({
        'open': prices,
        'high': [p + abs(step) for p in prices],
        'low': [p - abs(step) for p in prices],
        'close': prices,
        'volume': [1000] * n
    }, index=dates)


@pytest.mark.asyncio
async def test_compensation_adapter_opposite_side_creates_sell_intent_when_btc_buy():
    params = {
        "ema_fast": 5,
        "ema_slow": 20,
        "trend_threshold": 0.001,
        "btc_deposit_prct": 0.05,
        "btc_stop_loss_pct": 0.012,
        "eth_deposit_prct": 0.1,
        "eth_stop_loss_pct": 0.01,
        "compensation_threshold": 0.0025,
        "impulse_threshold": 0.004,
        "candles_against_threshold": 2,
        "compensation_delay_candles": 1,
        "eth_compensation_opposite": True,
        "interval": "1m",
    }
    strategy = CompensationStrategy(StrategyParameters(raw=params))

    # BTC падает (против BUY), ETH тоже падает (для opposite не важно, emergency путь)
    btc_df = make_trend_df(100, -0.5, 60)
    eth_df = make_trend_df(2000, -2.0, 60)

    template = MagicMock()
    template.interval = "1m"
    adapter = CompensationAdapter(strategy, template, deal_service=None)

    # Открытая BTC позиция BUY
    open_state = {
        "BTCUSDT": {
            "position": {
                "side": "BUY",
                "entry_price": 100.0,
                "entry_time": btc_df.index[-10],
            }
        }
    }

    # Подготовим состояние, будто сигнал уже был замечен ранее
    strategy.update_state(
        btc_deal_id=1,
        btc_entry_price=100.0,
        btc_entry_time=btc_df.index[-10],
        btc_side="BUY",
    )
    # Считаем, что окно ожидания уже началось несколько свечей назад
    strategy.state.compensation_signal_time = btc_df.index[-5]

    md = {"BTCUSDT": btc_df, "ETHUSDT": eth_df}
    decision = await adapter.decide(md, template, open_state)

    # Проверяем, что создан intent на ETH SELL
    intents = decision.intents
    assert any(i.symbol == "ETHUSDT" and i.side == "SELL" and i.role == "compensation" for i in intents)


@pytest.mark.asyncio
async def test_compensation_adapter_same_side_creates_buy_intent_when_btc_buy():
    params = {
        "ema_fast": 5,
        "ema_slow": 20,
        "trend_threshold": 0.001,
        "btc_deposit_prct": 0.05,
        "btc_stop_loss_pct": 0.012,
        "eth_deposit_prct": 0.1,
        "eth_stop_loss_pct": 0.01,
        "compensation_threshold": 0.0025,
        "impulse_threshold": 0.004,
        "candles_against_threshold": 2,
        "compensation_delay_candles": 1,
        "eth_compensation_opposite": False,
        "interval": "1m",
    }
    strategy = CompensationStrategy(StrategyParameters(raw=params))

    btc_df = make_trend_df(100, -0.5, 60)  # движение против BUY
    eth_df = make_trend_df(2000, 2.0, 60)  # для same ETH растет

    template = MagicMock()
    template.interval = "1m"
    adapter = CompensationAdapter(strategy, template, deal_service=None)

    open_state = {
        "BTCUSDT": {
            "position": {
                "side": "BUY",
                "entry_price": 100.0,
                "entry_time": btc_df.index[-10],
            }
        }
    }

    strategy.update_state(
        btc_deal_id=1,
        btc_entry_price=100.0,
        btc_entry_time=btc_df.index[-10],
        btc_side="BUY",
    )
    strategy.state.compensation_signal_time = btc_df.index[-5]

    md = {"BTCUSDT": btc_df, "ETHUSDT": eth_df}
    decision = await adapter.decide(md, template, open_state)

    intents = decision.intents
    assert any(i.symbol == "ETHUSDT" and i.side == "BUY" and i.role == "compensation" for i in intents)


