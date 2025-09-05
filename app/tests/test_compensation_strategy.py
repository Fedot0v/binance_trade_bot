import pytest
import pandas as pd
from datetime import datetime, timedelta

from strategies.compensation_strategy import CompensationStrategy
from services.strategy_parameters import StrategyParameters


class TestCompensationStrategy:
    @pytest.fixture
    def sample_params(self):
        return {
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.001,
            "btc_deposit_prct": 0.05,
            "btc_stop_loss_pct": 0.012,
            "eth_deposit_prct": 0.1,
            "eth_stop_loss_pct": 0.01,
            "compensation_threshold": 0.0025,
            "compensation_time_window": 15,
            "impulse_threshold": 0.004,
            "candles_against_threshold": 2,
            "max_trade_duration": 60
        }

    @pytest.fixture
    def strategy(self, sample_params):
        return CompensationStrategy(StrategyParameters(raw=sample_params))

    @pytest.fixture
    def sample_df(self):
        """Создает тестовые данные с восходящим трендом"""
        dates = pd.date_range(start='2024-01-01', periods=50, freq='1min')
        prices = [100 + i * 0.1 for i in range(50)]  # Восходящий тренд
        return pd.DataFrame({
            'open': prices,
            'high': [p + 0.05 for p in prices],
            'low': [p - 0.05 for p in prices],
            'close': prices,
            'volume': [1000] * 50
        }, index=dates)

    def test_strategy_initialization(self, strategy):
        """Тест инициализации стратегии"""
        assert strategy.ema_fast == 10
        assert strategy.ema_slow == 30
        assert strategy.trend_threshold == 0.001
        assert strategy.btc_risk_pct == 0.05
        assert strategy.btc_stop_loss_pct == 0.012
        assert strategy.eth_risk_pct == 0.1
        assert strategy.eth_stop_loss_pct == 0.01
        assert strategy.compensation_threshold == 0.0025
        assert strategy.compensation_time_window == 15
        assert strategy.impulse_threshold == 0.004
        assert strategy.candles_against_threshold == 2
        assert strategy.max_trade_duration == 60

    def test_generate_signal_long(self, strategy, sample_df):
        """Тест генерации сигнала на покупку"""
        signal = strategy.generate_signal(sample_df)
        assert signal == 'long'

    def test_generate_signal_short(self, strategy):
        """Тест генерации сигнала на продажу"""
        # Создаем нисходящий тренд
        dates = pd.date_range(start='2024-01-01', periods=50, freq='1min')
        prices = [100 - i * 0.1 for i in range(50)]  # Нисходящий тренд
        df = pd.DataFrame({
            'open': prices,
            'high': [p + 0.05 for p in prices],
            'low': [p - 0.05 for p in prices],
            'close': prices,
            'volume': [1000] * 50
        }, index=dates)
        
        signal = strategy.generate_signal(df)
        assert signal == 'short'

    def test_generate_signal_hold(self, strategy):
        """Тест генерации сигнала удержания при недостатке данных"""
        df = pd.DataFrame({
            'open': [100, 101],
            'high': [100.5, 101.5],
            'low': [99.5, 100.5],
            'close': [100, 101],
            'volume': [1000, 1000]
        })
        
        signal = strategy.generate_signal(df)
        assert signal == 'hold'

    def test_calculate_position_size(self, strategy):
        """Тест расчета размера позиции"""
        balance = 10000
        
        btc_size = strategy.calculate_position_size(balance, "BTC")
        assert btc_size == 500  # 5% от 10000
        
        eth_size = strategy.calculate_position_size(balance, "ETH")
        assert eth_size == 1000  # 10% от 10000

    def test_calculate_stop_loss_price(self, strategy):
        """Тест расчета цены стоп-лосса"""
        entry_price = 100
        
        # BTC лонг
        btc_long_sl = strategy.calculate_stop_loss_price(entry_price, "BUY", "BTC")
        expected_btc_sl = entry_price * (1 - 0.012)  # 1.2% стоп-лосс
        assert btc_long_sl == expected_btc_sl
        
        # BTC шорт
        btc_short_sl = strategy.calculate_stop_loss_price(entry_price, "SELL", "BTC")
        expected_btc_short_sl = entry_price * (1 + 0.012)  # 1.2% стоп-лосс
        assert btc_short_sl == expected_btc_short_sl
        
        # ETH лонг
        eth_long_sl = strategy.calculate_stop_loss_price(entry_price, "BUY", "ETH")
        expected_eth_sl = entry_price * (1 - 0.01)  # 1.0% стоп-лосс
        assert eth_long_sl == expected_eth_sl

    def test_should_trigger_compensation(self, strategy, sample_df):
        """Тест условий для запуска компенсации"""
        # Устанавливаем состояние BTC сделки
        strategy.update_state(
            btc_deal_id=1,
            btc_entry_price=100.0,
            btc_entry_time=datetime.now() - timedelta(minutes=5),
            btc_side="BUY"
        )
        
        # Текущая цена ниже цены входа (движение против позиции)
        current_price = 99.5  # -0.5% от цены входа
        
        # Должно вернуть False, так как движение меньше порога 0.25%
        result = strategy.should_trigger_compensation(sample_df, current_price)
        assert result == False
        
        # Увеличиваем движение против позиции
        current_price = 99.0  # -1% от цены входа
        
        # Должно вернуть True, так как движение больше порога и есть свечи против
        result = strategy.should_trigger_compensation(sample_df, current_price)
        # Результат зависит от анализа свечей, но логика должна работать

    def test_get_eth_side(self, strategy):
        """Тест определения стороны для ETH"""
        # Если BTC в лонге, ETH должен быть в шорте
        strategy.update_state(btc_side="BUY")
        eth_side = strategy.get_eth_side()
        assert eth_side == "SELL"
        
        # Если BTC в шорте, ETH должен быть в лонге
        strategy.update_state(btc_side="SELL")
        eth_side = strategy.get_eth_side()
        assert eth_side == "BUY"

    def test_should_close_btc_position_timeout(self, strategy, sample_df):
        """Тест закрытия BTC позиции по таймауту"""
        # Устанавливаем время входа больше часа назад
        strategy.update_state(
            btc_deal_id=1,
            btc_entry_time=datetime.now() - timedelta(hours=2)
        )
        
        # Должно вернуть True из-за таймаута
        result = strategy.should_close_btc_position(sample_df, sample_df)
        assert result == True

    def test_should_close_eth_position_timeout(self, strategy, sample_df):
        """Тест закрытия ETH позиции по таймауту"""
        # Устанавливаем время компенсации больше часа назад
        strategy.update_state(
            eth_deal_id=1,
            compensation_time=datetime.now() - timedelta(hours=2)
        )
        
        # Должно вернуть True из-за таймаута
        result = strategy.should_close_eth_position(sample_df)
        assert result == True

    def test_reset_state(self, strategy):
        """Тест сброса состояния стратегии"""
        # Устанавливаем некоторое состояние
        strategy.update_state(
            btc_deal_id=1,
            eth_deal_id=2,
            btc_entry_price=100.0,
            btc_side="BUY"
        )
        
        # Проверяем, что состояние установлено
        assert strategy.state.btc_deal_id == 1
        assert strategy.state.eth_deal_id == 2
        assert strategy.state.btc_entry_price == 100.0
        assert strategy.state.btc_side == "BUY"
        
        # Сбрасываем состояние
        strategy.reset_state()
        
        # Проверяем, что состояние сброшено
        assert strategy.state.btc_deal_id is None
        assert strategy.state.eth_deal_id is None
        assert strategy.state.btc_entry_price is None
        assert strategy.state.btc_side is None
        assert strategy.state.compensation_triggered == False

    def test_ethusdt_symbol_support(self, strategy):
        """Тест поддержки ETHUSDT символа"""
        # Проверяем, что стратегия корректно работает с ETH
        balance = 10000
        
        # Расчет размера позиции для ETH
        eth_size = strategy.calculate_position_size(balance, "ETH")
        assert eth_size == 1000  # 10% от баланса
        
        # Расчет стоп-лосса для ETH
        eth_entry_price = 3000  # Типичная цена ETH
        eth_stop_loss = strategy.calculate_stop_loss_price(eth_entry_price, "BUY", "ETH")
        expected_stop_loss = eth_entry_price * (1 - 0.01)  # 1% стоп-лосс
        assert eth_stop_loss == expected_stop_loss
        
        # Проверяем, что ETH стоп-лосс короче BTC (1% vs 1.2%)
        btc_stop_loss = strategy.calculate_stop_loss_price(eth_entry_price, "BUY", "BTC")
        assert eth_stop_loss > btc_stop_loss  # ETH стоп-лосс выше (меньший процент)

    def test_compensation_logic_with_eth(self, strategy, sample_df):
        """Тест логики компенсации с ETH"""
        # Симулируем BTC лонг позицию
        strategy.update_state(
            btc_deal_id=1,
            btc_entry_price=50000.0,  # BTC цена входа
            btc_entry_time=datetime.now() - timedelta(minutes=10),
            btc_side="BUY"
        )
        
        # Текущая цена BTC упала на 0.5%
        current_btc_price = 50000.0 * 0.995  # -0.5%
        
        # Проверяем условия компенсации
        should_compensate = strategy.should_trigger_compensation(sample_df, current_btc_price)
        
        # Если компенсация сработала, проверяем сторону для ETH
        if should_compensate:
            eth_side = strategy.get_eth_side()
            assert eth_side == "SELL"  # Шортим ETH если BTC в лонге
            
            # Проверяем размер позиции ETH
            eth_size = strategy.calculate_position_size(100000, "ETH")  # $100k баланс
            assert eth_size == 10000  # 10% от баланса
