import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

from strategies.novichok_strategy import NovichokStrategy
from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters


class TestNovichokStrategy:
    @pytest.fixture
    def strategy_params(self):
        return StrategyParameters({
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.001,
            "deposit_prct": 0.05,  # 5% в долях
            "stop_loss_pct": 0.02  # 2% в долях
        })

    @pytest.fixture
    def strategy(self, strategy_params):
        return NovichokStrategy(strategy_params)

    @pytest.fixture
    def sample_data_long_trend(self):
        """Данные с восходящим трендом"""
        np.random.seed(42)
        base_price = 50000
        trend = np.linspace(0, 1000, 50)  # Восходящий тренд
        noise = np.random.normal(0, 100, 50)
        prices = base_price + trend + noise
        
        return pd.DataFrame({
            'open': prices - 50,
            'high': prices + 100,
            'low': prices - 100,
            'close': prices,
            'volume': np.random.randint(100, 200, 50)
        })

    @pytest.fixture
    def sample_data_short_trend(self):
        """Данные с нисходящим трендом"""
        np.random.seed(42)
        base_price = 50000
        trend = np.linspace(0, -1000, 50)  # Нисходящий тренд
        noise = np.random.normal(0, 100, 50)
        prices = base_price + trend + noise
        
        return pd.DataFrame({
            'open': prices - 50,
            'high': prices + 100,
            'low': prices - 100,
            'close': prices,
            'volume': np.random.randint(100, 200, 50)
        })

    @pytest.fixture
    def sample_data_sideways(self):
        """Данные с боковым движением"""
        np.random.seed(42)
        base_price = 50000
        noise = np.random.normal(0, 50, 50)  # Минимальный шум
        prices = base_price + noise
        
        return pd.DataFrame({
            'open': prices - 25,
            'high': prices + 50,
            'low': prices - 50,
            'close': prices,
            'volume': np.random.randint(100, 200, 50)
        })

    def test_strategy_initialization(self, strategy_params):
        """Тест инициализации стратегии"""
        strategy = NovichokStrategy(strategy_params)
        
        assert strategy.ema_fast == 10
        assert strategy.ema_slow == 30
        assert strategy.trend_threshold == 0.001
        assert strategy.risk_pct == 0.05  # 5% в долях
        assert strategy.stop_loss_pct == 0.02

    def test_strategy_initialization_default_values(self):
        """Тест инициализации с дефолтными значениями"""
        params = StrategyParameters({})
        strategy = NovichokStrategy(params)
        
        assert strategy.ema_fast == 10  # дефолтное значение
        assert strategy.ema_slow == 30  # дефолтное значение
        assert strategy.trend_threshold == 0.001  # дефолтное значение
        assert strategy.risk_pct == 0.05  # дефолтное значение (5% в долях)
        assert strategy.stop_loss_pct == 0.02  # дефолтное значение

    def test_generate_signal_long_trend(self, strategy, sample_data_long_trend):
        """Тест генерации сигнала на покупку при восходящем тренде"""
        signal = strategy.generate_signal(sample_data_long_trend)
        assert signal == 'long'

    def test_generate_signal_short_trend(self, strategy, sample_data_short_trend):
        """Тест генерации сигнала на продажу при нисходящем тренде"""
        signal = strategy.generate_signal(sample_data_short_trend)
        assert signal == 'short'

    def test_generate_signal_sideways(self, strategy, sample_data_sideways):
        """Тест генерации сигнала hold при боковом движении"""
        signal = strategy.generate_signal(sample_data_sideways)
        assert signal == 'hold'

    def test_generate_signal_insufficient_data(self, strategy):
        """Тест генерации сигнала при недостаточном количестве данных"""
        # Создаем DataFrame с недостаточным количеством данных
        insufficient_data = pd.DataFrame({
            'close': [50000, 50100, 50200],  # Меньше чем ema_slow (30)
            'open': [49950, 50050, 50150],
            'high': [50100, 50200, 50300],
            'low': [49900, 50000, 50100],
            'volume': [100, 110, 120]
        })
        
        signal = strategy.generate_signal(insufficient_data)
        assert signal == 'hold'

    def test_generate_signal_trend_threshold(self, strategy):
        """Тест влияния порога тренда на генерацию сигнала"""
        # Создаем данные с очень слабым трендом
        weak_trend_data = pd.DataFrame({
            'close': [50000 + i * 0.1 for i in range(50)],  # Очень слабый тренд
            'open': [50000 + i * 0.1 - 25 for i in range(50)],
            'high': [50000 + i * 0.1 + 50 for i in range(50)],
            'low': [50000 + i * 0.1 - 50 for i in range(50)],
            'volume': [100] * 50
        })
        
        signal = strategy.generate_signal(weak_trend_data)
        assert signal == 'hold'  # Должен быть hold из-за слабого тренда

    def test_calculate_position_size(self, strategy):
        """Тест расчета размера позиции"""
        balance = 10000.0
        position_size = strategy.calculate_position_size(balance)
        
        expected_size = balance * strategy.risk_pct  # risk_pct теперь в долях
        assert position_size == expected_size
        assert position_size == 500.0  # 5% от 10000 (0.05 * 10000)

    def test_calculate_position_size_zero_balance(self, strategy):
        """Тест расчета размера позиции при нулевом балансе"""
        balance = 0.0
        position_size = strategy.calculate_position_size(balance)
        
        assert position_size == 0.0

    def test_calculate_position_size_negative_balance(self, strategy):
        """Тест расчета размера позиции при отрицательном балансе"""
        balance = -1000.0
        position_size = strategy.calculate_position_size(balance)
        
        expected_size = balance * strategy.risk_pct  # risk_pct теперь в долях
        assert position_size == expected_size
        assert position_size == -50.0  # -1000 * 0.05
    
    def test_calculate_stop_loss_price_long(self, strategy):
        """Тест расчета цены стоп-лосса для длинной позиции"""
        entry_price = 50000.0
        side = "BUY"
        stop_loss_price = strategy.calculate_stop_loss_price(entry_price, side)
        expected_price = entry_price * (1 - 0.02)  # 2% стоп-лосс
        assert stop_loss_price == expected_price
    
    def test_calculate_stop_loss_price_short(self, strategy):
        """Тест расчета цены стоп-лосса для короткой позиции"""
        entry_price = 50000.0
        side = "SELL"
        stop_loss_price = strategy.calculate_stop_loss_price(entry_price, side)
        expected_price = entry_price * (1 + 0.02)  # 2% стоп-лосс
        assert stop_loss_price == expected_price

    def test_ema_calculation(self, strategy, sample_data_long_trend):
        """Тест корректности расчета EMA"""
        df = sample_data_long_trend
        
        ema_fast_manual = df['close'].ewm(span=strategy.ema_fast).mean()
        ema_slow_manual = df['close'].ewm(span=strategy.ema_slow).mean()
        
        last_fast = ema_fast_manual.iloc[-1]
        last_slow = ema_slow_manual.iloc[-1]
        
        signal = strategy.generate_signal(df)
        
        if last_fast > last_slow:
            assert signal in ['long', 'hold']
        elif last_fast < last_slow:
            assert signal in ['short', 'hold']
        else:
            assert signal == 'hold'

    def test_strategy_parameters_validation(self):
        """Тест валидации параметров стратегии"""
        params = StrategyParameters({
            "ema_fast": -10,
            "ema_slow": 0,
            "trend_threshold": -0.001,
            "deposit_prct": 1.5,
            "stop_loss_pct": 0.5
        })
        
        # Стратегия использует параметры как есть (без валидации)
        strategy = NovichokStrategy(params)
        
        assert strategy.ema_fast == -10  # Использует переданное значение
        assert strategy.ema_slow == 0    # Использует переданное значение
        assert strategy.trend_threshold == -0.001  # Использует переданное значение
        assert strategy.risk_pct == 1.5  # Использует переданное значение (150% в долях)
        assert strategy.stop_loss_pct == 0.5  # Использует переданное значение (50% в долях)


class TestBaseStrategy:
    def test_base_strategy_abstract_methods(self):
        """Тест того, что BaseStrategy является абстрактным классом"""
        # Нельзя создать экземпляр абстрактного класса
        with pytest.raises(TypeError):
            BaseStrategy()

    def test_base_strategy_inheritance(self, strategy_parameters):
        """Тест наследования от BaseStrategy"""
        strategy = NovichokStrategy(strategy_parameters)
        
        assert isinstance(strategy, BaseStrategy)
        assert hasattr(strategy, 'generate_signal')
        assert hasattr(strategy, 'calculate_position_size')
        
        # Проверяем, что методы можно вызвать
        assert callable(strategy.generate_signal)
        assert callable(strategy.calculate_position_size)


class TestStrategyParameters:
    def test_strategy_parameters_get_int(self):
        """Тест получения целочисленных параметров"""
        params = StrategyParameters({
            "test_int": 42,
            "test_string": "not_an_int"
        })
        
        assert params.get_int("test_int", 0) == 42
        assert params.get_int("test_string", 10) == 10  # дефолтное значение
        assert params.get_int("non_existent", 5) == 5   # дефолтное значение

    def test_strategy_parameters_get_float(self):
        """Тест получения параметров с плавающей точкой"""
        params = StrategyParameters({
            "test_float": 3.14,
            "test_int": 42
        })
        
        assert params.get_float("test_float", 0.0) == 3.14
        assert params.get_float("test_int", 1.0) == 42.0  # конвертация int в float
        assert params.get_float("non_existent", 2.5) == 2.5  # дефолтное значение

    def test_strategy_parameters_as_dict(self):
        """Тест конвертации параметров в словарь"""
        original_params = {
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.001
        }
        params = StrategyParameters(original_params)
        
        result_dict = params.as_dict()
        assert result_dict == original_params 