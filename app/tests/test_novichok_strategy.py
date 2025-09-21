import pandas as pd
import numpy as np
import pytest

from strategies.novichok_strategy import NovichokStrategy
from services.strategy_parameters import StrategyParameters


def make_df(prices: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        'open': prices,
        'high': [p * 1.001 for p in prices],
        'low':  [p * 0.999 for p in prices],
        'close': prices,
        'volume': [100] * len(prices)
    })


def test_generate_signal_insufficient_data():
    params = StrategyParameters(raw={
        'ema_fast': 5,
        'ema_slow': 20,
        'trend_threshold': 0.001,
        'deposit_prct': 0.05,
    })
    s = NovichokStrategy(params)
    df = make_df([100 + i for i in range(10)])  # len < ema_slow
    assert s.generate_signal(df) is None


def test_generate_signal_trend_long_short():
    params = StrategyParameters(raw={
        'ema_fast': 5,
        'ema_slow': 10,
        'trend_threshold': 0.0001,
        'deposit_prct': 0.05,
    })
    s = NovichokStrategy(params)

    up = make_df([100 + i for i in range(50)])
    down = make_df([100 - i for i in range(50)])

    assert s.generate_signal(up) == 'long'
    assert s.generate_signal(down) == 'short'


def test_position_size_and_levels():
    params = StrategyParameters(raw={
        'ema_fast': 5,
        'ema_slow': 10,
        'trend_threshold': 0.001,
        'deposit_prct': 0.07,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.03,
        'trailing_stop_pct': 0.005,
    })
    s = NovichokStrategy(params)

    balance = 1000.0
    size = s.calculate_position_size(balance)
    assert pytest.approx(size, rel=1e-6) == 70.0

    entry = 100.0

    sl_long = s.calculate_stop_loss_price(entry, 'long', 'BTCUSDT')
    tp_long = s.calculate_take_profit_price(entry, 'long', 'BTCUSDT')
    assert pytest.approx(sl_long, rel=1e-6) == 98.0
    assert pytest.approx(tp_long, rel=1e-6) == 103.0

    sl_short = s.calculate_stop_loss_price(entry, 'short', 'BTCUSDT')
    tp_short = s.calculate_take_profit_price(entry, 'short', 'BTCUSDT')
    assert pytest.approx(sl_short, rel=1e-6) == 102.0
    assert pytest.approx(tp_short, rel=1e-6) == 97.0


def test_trailing_stop_prices():
    params = StrategyParameters(raw={
        'ema_fast': 5,
        'ema_slow': 10,
        'trend_threshold': 0.001,
        'deposit_prct': 0.05,
        'trailing_stop_pct': 0.01,
    })
    s = NovichokStrategy(params)

    entry = 100.0
    current_up = 110.0
    current_down = 90.0

    ts_long = s.calculate_trailing_stop_price(entry, current_up, 'long', 'BTCUSDT')
    assert pytest.approx(ts_long, rel=1e-6) == 108.9  # 110 * (1 - 0.01)

    ts_short = s.calculate_trailing_stop_price(entry, current_down, 'short', 'BTCUSDT')
    assert pytest.approx(ts_short, rel=1e-6) == 90.9   # 90 * (1 + 0.01)


