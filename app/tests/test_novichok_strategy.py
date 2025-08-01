import pytest
import pandas as pd
from strategies.novichok_strategy import NovichokStrategy

@pytest.fixture
def fake_market_data():
    # Пример исторических цен
    return {
        "close": [30000, 30100, 29900, 30500, 30700, 30800, 30900, 30700, 30850, 30910, 31000, 31100],
        "open": [29950, 30050, 29900, 30450, 30600, 30750, 30800, 30600, 30800, 30890, 30950, 31010],
        "high": [30100, 30150, 29950, 30550, 30800, 30900, 31000, 30800, 30900, 31000, 31120, 31200],
        "low":  [29900, 29950, 29800, 30400, 30500, 30700, 30800, 30600, 30700, 30800, 30900, 30980],
        "volume": [100, 120, 110, 130, 140, 150, 160, 120, 130, 140, 150, 155],
    }

@pytest.fixture
def sample_strategy_params():
    return {
        "ema_fast": 3,
        "ema_slow": 6,
        "risk_pct": 0.05,
        "trend_threshold": 0.001  # Добавь если используется
    }

def test_strategy_signal_generation(fake_market_data, sample_strategy_params):
    strat = NovichokStrategy(sample_strategy_params)
    df = pd.DataFrame(fake_market_data)
    signal = strat.generate_signal(df)
    assert signal in ["long", "short", "hold"]
