import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

from strategies.novichok_strategy import NovichokStrategy
from services.strategy_parameters import StrategyParameters


@pytest.fixture
def sample_strategy_params():
    return StrategyParameters({
        "ema_fast": 10,
        "ema_slow": 30,
        "trend_threshold": 0.001,
        "deposit_prct": 0.05,  # 5% в долях
        "stop_loss_pct": 0.02  # 2% в долях
    })


def test_strategy_signal_generation(sample_strategy_params):
    """Тест генерации сигнала стратегией"""
    strat = NovichokStrategy(sample_strategy_params)
    
    data = pd.DataFrame({
        'close': [50000 + i * 10 for i in range(50)],
        'open': [50000 + i * 10 - 5 for i in range(50)],
        'high': [50000 + i * 10 + 10 for i in range(50)],
        'low': [50000 + i * 10 - 10 for i in range(50)],
        'volume': [100] * 50
    })
    
    signal = strat.generate_signal(data)
    
    assert signal in ['long', 'short', 'hold']
