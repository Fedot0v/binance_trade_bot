import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

from services.backtest.universal_backtest_engine import UniversalBacktestEngine, BacktestContext
from strategies.compensation_strategy import CompensationStrategy
from strategies.compensation_adapter import CompensationAdapter
from services.strategy_parameters import StrategyParameters


@pytest.fixture
def sample_btc_market_data():
    dates = pd.date_range('2023-01-01', periods=120, freq='1min')
    close_prices = np.linspace(50000, 50120, 120) + np.random.normal(0, 5, 120)
    return pd.DataFrame({
        'open': close_prices - 5, 'high': close_prices + 5,
        'low': close_prices - 5, 'close': close_prices,
        'volume': np.random.uniform(100, 500, 120)
    }, index=dates)


@pytest.fixture
def sample_eth_market_data():
    dates = pd.date_range('2023-01-01', periods=120, freq='1min')
    close_prices = np.linspace(2000, 2024, 120) + np.random.normal(0, 2, 120)
    return pd.DataFrame({
        'open': close_prices - 2, 'high': close_prices + 2,
        'low': close_prices - 2, 'close': close_prices,
        'volume': np.random.uniform(1000, 5000, 120)
    }, index=dates)


@pytest.fixture
def compensation_template():
    return MagicMock(
        id=2,
        template_name="Compensation",
        leverage=10,
        interval="1m",
        parameters={
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.001,
            "btc_deposit_prct": 0.05,
            "btc_stop_loss_pct": 0.012,
            "btc_take_profit_pct": 0.03,
            "btc_leverage": 10,
            "eth_deposit_prct": 0.1,
            "eth_stop_loss_pct": 0.01,
            "eth_take_profit_pct": 0.015,
            "eth_leverage": 10,
            "compensation_threshold": 0.005,
            "compensation_delay_candles": 3,
            "impulse_threshold": 0.004,
            "candles_against_threshold": 2,
            "trailing_stop_pct": 0.003,
            "eth_compensation_opposite": True,
        }
    )


@pytest.mark.asyncio
async def test_compensation_engine_runs_with_adapter(sample_btc_market_data, sample_eth_market_data, compensation_template):
    params = StrategyParameters(raw={**compensation_template.parameters, "interval": compensation_template.interval})
    strategy = CompensationStrategy(params)
    adapter = CompensationAdapter(strategy, compensation_template, deal_service=None)

    market_data = {"BTCUSDT": sample_btc_market_data, "ETHUSDT": sample_eth_market_data}

    context = BacktestContext(
        strategy=adapter,
        template=compensation_template,
        initial_balance=10000.0,
        market_data=market_data,
        config={"fee_rate": 0.0, "slippage_bps": 0.0, "spread_bps": 0.0},
        leverage=1,
    )
    engine = UniversalBacktestEngine(context)
    result = await engine.run()

    assert result is not None
    assert hasattr(result, 'final_balance')
    assert hasattr(result, 'trades')
    assert result.total_trades >= 0
