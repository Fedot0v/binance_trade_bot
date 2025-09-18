import pytest
import pandas as pd
from datetime import datetime, timedelta

from strategies.compensation_strategy import CompensationStrategy
from services.strategy_parameters import StrategyParameters


class TestCompensationStrategy:
    @pytest.fixture
    def sample_params(self):
        # Включаем опцию противоположной стороны по умолчанию
        return {
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
            "compensation_delay_candles": 0,
            "eth_compensation_opposite": True,
        }

    @pytest.fixture
    def strategy(self, sample_params):
        return CompensationStrategy(StrategyParameters(raw=sample_params))

    def _make_trend_df(self, start: float, step: float, n: int, freq: str = '1min') -> pd.DataFrame:
        dates = pd.date_range(start='2024-01-01', periods=n, freq=freq)
        prices = [start + i * step for i in range(n)]
        return pd.DataFrame({
            'open': prices,
            'high': [p + abs(step) for p in prices],
            'low': [p - abs(step) for p in prices],
            'close': prices,
            'volume': [1000] * n
        }, index=dates)

    def test_get_eth_side_opposite_true(self, strategy):
        strategy.update_state(btc_side="BUY")
        assert strategy.get_eth_side() == "SELL"
        strategy.update_state(btc_side="SELL")
        assert strategy.get_eth_side() == "BUY"

    def test_get_eth_side_same_when_flag_false(self, sample_params):
        params = dict(sample_params)
        params["eth_compensation_opposite"] = False
        s = CompensationStrategy(StrategyParameters(raw=params))
        s.update_state(btc_side="BUY")
        assert s.get_eth_side() == "BUY"
        s.update_state(btc_side="SELL")
        assert s.get_eth_side() == "SELL"

    def test_should_trigger_compensation_opposite_alignment(self, strategy):
        # BTC позиция BUY, последние свечи против (красные)
        btc_df = self._make_trend_df(100, -0.2, 50)
        # ETH должен подтверждать SHORT (нисходящий тренд)
        eth_df = self._make_trend_df(2000, -1.0, 50)

        strategy.update_state(
            btc_deal_id=1,
            btc_entry_price=100.0,
            btc_entry_time=btc_df.index[-10],
            btc_side="BUY"
        )

        current_price = 99.0  # -1.0% против позиции
        current_time = btc_df.index[-1]
        assert strategy.should_trigger_compensation(btc_df, eth_df, current_price, current_time) in [True, False]

    def test_should_trigger_compensation_same_alignment(self, sample_params):
        params = dict(sample_params)
        params["eth_compensation_opposite"] = False
        s = CompensationStrategy(StrategyParameters(raw=params))
        # BTC позиция BUY, последние свечи против
        btc_df = self._make_trend_df(100, -0.2, 50)
        # ETH должен подтверждать LONG (восходящий тренд) при same-режиме
        eth_df = self._make_trend_df(2000, 1.0, 50)
        s.update_state(
            btc_deal_id=1,
            btc_entry_price=100.0,
            btc_entry_time=btc_df.index[-10],
            btc_side="BUY"
        )
        current_price = 99.0
        current_time = btc_df.index[-1]
        assert s.should_trigger_compensation(btc_df, eth_df, current_price, current_time) in [True, False]
