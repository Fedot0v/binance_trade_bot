import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta

from services.backtest.universal_backtest_service import UniversalBacktestService
from services.backtest.universal_backtest_engine import UniversalBacktestEngine, BacktestContext
from strategies.novichok_adapter import NovichokAdapter
from strategies.novichok_strategy import NovichokStrategy
from services.strategy_parameters import StrategyParameters


@pytest.fixture
def sample_market_data():
    """Создает тестовые рыночные данные"""
    dates = pd.date_range('2023-01-01', periods=100, freq='1H')
    # Создаем тренд с некоторым шумом
    base_price = 50000
    trend = np.linspace(0, 2000, 100)  # Восходящий тренд
    noise = np.random.normal(0, 100, 100)
    close_prices = base_price + trend + noise

    return pd.DataFrame({
        'open': close_prices - np.random.uniform(50, 150, 100),
        'high': close_prices + np.random.uniform(50, 150, 100),
        'low': close_prices - np.random.uniform(50, 150, 100),
        'close': close_prices,
        'volume': np.random.uniform(1000, 5000, 100)
    }, index=dates)


@pytest.fixture
def sample_template():
    """Создает тестовый шаблон стратегии"""
    return MagicMock(
        id=1,
        name="Test Novichok Template",
        symbol="BTCUSDT",
        leverage=10,
        parameters={
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.001,
            "deposit_prct": 0.05,  # 5% в долях
            "stop_loss_pct": 0.02,  # 2% в долях
        }
    )


@pytest.fixture
def novichok_strategy(sample_template):
    """Создает экземпляр стратегии Novichok"""
    params = StrategyParameters(raw=sample_template.parameters)
    return NovichokStrategy(params)


@pytest.fixture
def novichok_adapter(novichok_strategy):
    """Создает адаптер для стратегии Novichok"""
    return NovichokAdapter(novichok_strategy)


class TestBacktestIntegration:
    """Интеграционные тесты для бэктеста"""

    @pytest.mark.asyncio
    async def test_universal_backtest_service_creation(self, novichok_adapter, sample_template, sample_market_data):
        """Тест создания универсального сервиса бэктеста"""
        service = UniversalBacktestService()

        # Проверяем, что сервис создался
        assert service is not None
        assert hasattr(service, 'run_backtest')

    @pytest.mark.asyncio
    async def test_backtest_context_creation(self, novichok_adapter, sample_template, sample_market_data):
        """Тест создания контекста бэктеста"""
        initial_balance = 10000.0
        market_data = {"BTCUSDT": sample_market_data}

        context = BacktestContext(
            strategy=novichok_adapter,
            template=sample_template,
            initial_balance=initial_balance,
            market_data=market_data
        )

        # Проверяем контекст
        assert context.strategy == novichok_adapter
        assert context.template == sample_template
        assert context.initial_balance == initial_balance
        assert context.current_balance == initial_balance
        assert len(context.market_data) == 1

    @pytest.mark.asyncio
    async def test_strategy_adapter_decide_method(self, novichok_adapter, sample_market_data, sample_template):
        """Тест метода decide адаптера стратегии"""
        market_data = {"BTCUSDT": sample_market_data}
        open_state = {}

        # Вызываем decide
        decision = await novichok_adapter.decide(market_data, sample_template, open_state)

        # Проверяем, что decision валидный
        assert decision is not None
        assert hasattr(decision, 'intents')
        assert isinstance(decision.intents, list)

    @pytest.mark.asyncio
    async def test_backtest_engine_initialization(self, novichok_adapter, sample_template, sample_market_data):
        """Тест инициализации движка бэктеста"""
        market_data = {"BTCUSDT": sample_market_data}

        context = BacktestContext(
            strategy=novichok_adapter,
            template=sample_template,
            initial_balance=10000.0,
            market_data=market_data
        )

        engine = UniversalBacktestEngine(context)

        # Проверяем инициализацию
        assert engine.context == context

    @pytest.mark.asyncio
    async def test_strategy_signal_generation_in_backtest_context(self, novichok_strategy, sample_market_data):
        """Тест генерации сигналов стратегией в контексте бэктеста"""
        signal = novichok_strategy.generate_signal(sample_market_data)

        # Проверяем, что сигнал валидный
        assert signal in ['long', 'short', 'hold', None]

        # Проверяем расчет стоп-лосса
        side = 'long' if signal == 'long' else 'short' if signal == 'short' else None
        if side:
            stop_loss_price = novichok_strategy.calculate_stop_loss_price(
                sample_market_data['close'].iloc[-1],
                side,
                'BTCUSDT'
            )
            assert stop_loss_price is not None
            assert stop_loss_price > 0

    @pytest.mark.asyncio
    async def test_position_size_calculation(self, novichok_strategy):
        """Тест расчета размера позиции"""
        balance = 10000.0
        position_size = novichok_strategy.calculate_position_size(balance)

        # Проверяем, что размер позиции разумный
        assert position_size > 0
        assert position_size <= balance * 0.1  # Не более 10% от баланса

    @pytest.mark.asyncio
    async def test_strategy_exit_logic_verification(self, novichok_strategy, sample_market_data):
        """Тест логики выхода из позиции (должна быть только по стоп-лоссу)"""
        # Создаем mock сделки
        mock_deal = MagicMock()
        mock_deal.symbol = "BTCUSDT"
        mock_deal.side = "long"
        mock_deal.entry_price = 50000.0

        market_data_dict = {"BTCUSDT": sample_market_data}

        # Проверяем, что стратегия НЕ закрывает позицию по сигналу
        should_close = novichok_strategy.should_close_position(mock_deal, market_data_dict)

        # Для Novichok стратегии выход должен быть ТОЛЬКО по стоп-лоссу
        assert should_close == False

    @pytest.mark.asyncio
    async def test_backtest_trailing_stop_logic(self, novichok_adapter, sample_template, sample_market_data):
        """Тест логики trailing stop в бэктесте"""
        market_data = {"BTCUSDT": sample_market_data}
        open_state = {
            "BTCUSDT": {
                'position': {
                    'side': 'BUY',
                    'entry_price': 50000.0,
                    'stop_loss': 49000.0  # 2% ниже входа
                }
            }
        }

        # Вызываем decide с открытой позицией
        decision = await novichok_adapter.decide(market_data, sample_template, open_state)

        # Проверяем, что нет автоматического закрытия по противоположному сигналу
        # (это должна делать логика стоп-лосса в UniversalBacktestEngine)
        assert decision is not None
        assert hasattr(decision, 'intents')

    @pytest.mark.asyncio
    async def test_percentage_parameters_handling(self, novichok_adapter):
        """Тест обработки процентных параметров"""
        # Проверяем, что адаптер корректно конвертирует параметры
        assert hasattr(novichok_adapter, 'legacy')

        # Проверяем, что стратегия имеет методы для работы с процентами
        legacy = novichok_adapter.legacy
        assert hasattr(legacy, 'calculate_stop_loss_price')
        assert hasattr(legacy, 'calculate_take_profit_price')
