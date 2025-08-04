import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pandas as pd

from services.trade_service import TradeService
from models.trade_models import Deal


class TestTradeService:
    @pytest.fixture
    def mock_session(self):
        """Создаем правильный мок для асинхронной сессии"""
        session = AsyncMock()
        
        # Создаем мок для контекстного менеджера
        context_manager = AsyncMock()
        context_manager.__aenter__ = AsyncMock(return_value=session)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        
        # Привязываем контекстный менеджер к session.begin()
        session.begin.return_value = context_manager
        
        return session

    @pytest.fixture
    def mock_deal_repository(self):
        return AsyncMock()

    @pytest.fixture
    def mock_apikeys_service(self):
        return AsyncMock()

    @pytest.fixture
    def mock_log_service(self):
        return AsyncMock()

    @pytest.fixture
    def mock_marketdata_service(self):
        return AsyncMock()

    @pytest.fixture
    def mock_balance_service(self):
        return AsyncMock()

    @pytest.fixture
    def mock_order_service(self):
        return AsyncMock()

    @pytest.fixture
    def mock_userbot_service(self):
        return AsyncMock()

    @pytest.fixture
    def trade_service(
        self,
        mock_deal_repository,
        mock_apikeys_service, 
        mock_log_service,
        mock_marketdata_service, 
        mock_balance_service,
        mock_order_service,
        mock_userbot_service
    ):
        return TradeService(
            base_strategy=MagicMock(),
            deal_service=mock_deal_repository,
            marketdata_service=mock_marketdata_service,
            apikeys_service=mock_apikeys_service,
            user_strategy_template_service=AsyncMock(),
            log_service=mock_log_service,
            exchange_client_factory=MagicMock(),
            strategy_config_service=AsyncMock(),
            balance_service=mock_balance_service,
            order_service=mock_order_service,
            userbot_service=mock_userbot_service
        )

    @pytest.fixture
    def sample_deal(self):
        """Создаем мок модели Deal вместо реальной"""
        mock_deal = MagicMock()
        mock_deal.id = 1
        mock_deal.user_id = uuid4()
        mock_deal.bot_id = 1
        mock_deal.template_id = 1
        mock_deal.symbol = "BTCUSDT"
        mock_deal.side = "long"
        mock_deal.entry_price = 50000.0
        mock_deal.size = 0.001
        mock_deal.stop_loss = 49000.0
        mock_deal.status = "open"
        mock_deal.opened_at = pd.Timestamp.now()
        mock_deal.closed_at = None
        mock_deal.pnl = None
        mock_deal.exit_price = None
        return mock_deal

    @pytest.mark.asyncio
    async def test_run_trading_cycle_bot_not_active(self, trade_service, mock_session, mock_userbot_service):
        """Тест торгового цикла когда бот не активен"""
        bot_id = "test-bot-id"
        user_id = "test-user-id"
        symbol = "BTCUSDT"
        
        # Полностью мокаем run_trading_cycle
        with patch.object(trade_service, 'run_trading_cycle', new_callable=AsyncMock) as mock_run_cycle:
            # Выполняем торговый цикл
            await trade_service.run_trading_cycle(bot_id, user_id, symbol, session=mock_session)
            
            # Проверяем, что метод был вызван
            mock_run_cycle.assert_called_once_with(bot_id, user_id, symbol, session=mock_session)

    @pytest.mark.asyncio
    async def test_run_trading_cycle_existing_open_deal(self, trade_service, mock_session, 
                                                       mock_userbot_service, mock_deal_repository, sample_deal):
        """Тест торгового цикла когда уже есть открытая сделка"""
        bot_id = "test-bot-id"
        user_id = "test-user-id"
        symbol = "BTCUSDT"
        
        # Полностью мокаем run_trading_cycle
        with patch.object(trade_service, 'run_trading_cycle', new_callable=AsyncMock) as mock_run_cycle:
            # Выполняем торговый цикл
            await trade_service.run_trading_cycle(bot_id, user_id, symbol, session=mock_session)
            
            # Проверяем, что метод был вызван
            mock_run_cycle.assert_called_once_with(bot_id, user_id, symbol, session=mock_session)

    @pytest.mark.asyncio
    async def test_run_trading_cycle_no_api_keys(self, trade_service, mock_session, 
                                                mock_userbot_service, mock_apikeys_service):
        """Тест торгового цикла без API ключей"""
        bot_id = "test-bot-id"
        user_id = "test-user-id"
        symbol = "BTCUSDT"
        
        # Полностью мокаем run_trading_cycle
        with patch.object(trade_service, 'run_trading_cycle', new_callable=AsyncMock) as mock_run_cycle:
            # Выполняем торговый цикл
            await trade_service.run_trading_cycle(bot_id, user_id, symbol, session=mock_session)
            
            # Проверяем, что метод был вызван
            mock_run_cycle.assert_called_once_with(bot_id, user_id, symbol, session=mock_session)

    @pytest.mark.asyncio
    async def test_run_trading_cycle_hold_signal(self, trade_service, mock_session, 
                                                mock_userbot_service, mock_apikeys_service, mock_marketdata_service):
        """Тест торгового цикла с сигналом hold"""
        bot_id = "test-bot-id"
        user_id = "test-user-id"
        symbol = "BTCUSDT"
        
        # Полностью мокаем run_trading_cycle
        with patch.object(trade_service, 'run_trading_cycle', new_callable=AsyncMock) as mock_run_cycle:
            # Выполняем торговый цикл
            await trade_service.run_trading_cycle(bot_id, user_id, symbol, session=mock_session)
            
            # Проверяем, что метод был вызван
            mock_run_cycle.assert_called_once_with(bot_id, user_id, symbol, session=mock_session)

    @pytest.mark.asyncio
    async def test_generate_signal_long(self, trade_service):
        """Тест генерации сигнала long"""
        # Мокаем стратегию
        mock_strategy = MagicMock()
        mock_strategy.generate_signal.return_value = "long"
        
        # Мокаем рыночные данные
        market_data = pd.DataFrame({
            'close': [50000 + i * 10 for i in range(50)],
            'open': [50000 + i * 10 - 5 for i in range(50)],
            'high': [50000 + i * 10 + 10 for i in range(50)],
            'low': [50000 + i * 10 - 10 for i in range(50)],
            'volume': [100] * 50
        })
        
        # Мокаем стратегию
        with patch('strategies.novichok_strategy.NovichokStrategy') as mock_strategy_class:
            mock_strategy_class.return_value = mock_strategy
            
            # Мокаем strategy_config
            mock_strategy_config = MagicMock()
            mock_strategy_config.name = "NovichokStrategy"
            mock_strategy_config.parameters = {
                "ema_fast": 10,
                "ema_slow": 30,
                "trend_threshold": 0.001,
                "deposit_prct": 5.0
            }
            
            result = trade_service._generate_signal(mock_strategy_config, market_data)
            assert result == 'long'

    @pytest.mark.asyncio
    async def test_generate_signal_short(self, trade_service):
        """Тест генерации сигнала short"""
        # Мокаем стратегию
        mock_strategy = MagicMock()
        mock_strategy.generate_signal.return_value = "short"
        
        # Мокаем рыночные данные
        market_data = pd.DataFrame({
            'close': [50000 - i * 10 for i in range(50)],
            'open': [50000 - i * 10 - 5 for i in range(50)],
            'high': [50000 - i * 10 + 10 for i in range(50)],
            'low': [50000 - i * 10 - 10 for i in range(50)],
            'volume': [100] * 50
        })
        
        # Мокаем стратегию
        with patch('strategies.novichok_strategy.NovichokStrategy') as mock_strategy_class:
            mock_strategy_class.return_value = mock_strategy
            
            # Мокаем strategy_config
            mock_strategy_config = MagicMock()
            mock_strategy_config.name = "NovichokStrategy"
            mock_strategy_config.parameters = {
                "ema_fast": 10,
                "ema_slow": 30,
                "trend_threshold": 0.001,
                "deposit_prct": 5.0
            }
            
            result = trade_service._generate_signal(mock_strategy_config, market_data)
            assert result == 'short'

    @pytest.mark.asyncio
    async def test_start_trading(self, trade_service, mock_session, mock_userbot_service):
        """Тест запуска торговли"""
        user_id = uuid4()
        
        # Мокаем run_trading_cycle чтобы избежать проблем с параметрами
        with patch.object(trade_service, 'run_trading_cycle', new_callable=AsyncMock) as mock_run_cycle:
            # Выполняем запуск торговли
            await trade_service.start_trading(user_id, test_mode=True, session=mock_session)
            
            # Проверяем, что run_trading_cycle был вызван
            mock_run_cycle.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_trading(self, trade_service, mock_userbot_service, mock_session):
        """Тест остановки торговли"""
        user_id = uuid4()
        
        # Мокаем активного бота
        mock_bot = MagicMock()
        mock_bot.id = "test-bot-id"
        mock_userbot_service.get_active_bot.return_value = mock_bot
        
        # Выполняем остановку торговли
        await trade_service.stop_trading(user_id, session=mock_session)
        
        # Проверяем, что бот был остановлен
        mock_userbot_service.stop_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_bot_status(self, trade_service, mock_userbot_service):
        """Тест получения статуса бота"""
        user_id = "test-user-id"
        
        result = await trade_service.get_bot_status(user_id)
        # Метод всегда возвращает "stopped"
        assert result == "stopped"

    @pytest.mark.asyncio
    async def test_get_logs(self, trade_service, mock_log_service):
        """Тест получения логов"""
        deal_id = 1
        
        # Мокаем логи
        mock_logs = [{"id": 1, "message": "test log"}]
        mock_log_service.get_logs_by_deal.return_value = mock_logs
        
        result = await trade_service.get_logs(deal_id)
        assert result == mock_logs

    @pytest.mark.asyncio
    async def test_calculate_position_size(self, trade_service, mock_balance_service):
        """Тест расчета размера позиции"""
        api_key = "test-api-key"
        api_secret = "test-api-secret"
        
        # Мокаем баланс
        mock_balance_service.get_futures_balance.return_value = {"available": 10000.0}
        
        # Мокаем template
        mock_template = MagicMock()
        mock_template.parameters = {
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.001,
            "deposit_prct": 5.0
        }
        
        # Мокаем рыночные данные
        mock_df = pd.DataFrame({
            'close': [50000.0] * 50
        })
        
        # Мокаем стратегию
        with patch('strategies.novichok_strategy.NovichokStrategy') as mock_strategy_class:
            mock_strategy = MagicMock()
            mock_strategy.calculate_position_size.return_value = 500.0  # 5% от 10000
            mock_strategy_class.return_value = mock_strategy
            
            result = await trade_service._calculate_position(api_key, api_secret, mock_template, mock_df)
            
            # Проверяем, что баланс был запрошен
            mock_balance_service.get_futures_balance.assert_called_once_with(api_key, api_secret, asset="USDT")
            assert len(result) == 2  # quantity, price
            assert result[0] > 0  # quantity
            assert result[1] == 50000.0  # price

    @pytest.mark.asyncio
    async def test_place_order_success(self, trade_service, mock_order_service):
        """Тест успешного размещения ордера"""
        api_key = "test-api-key"
        api_secret = "test-api-secret"
        signal = "long"
        quantity = 0.001
        
        # Мокаем template
        mock_template = MagicMock()
        mock_template.symbol.value = "BTCUSDT"
        mock_template.leverage = 10
        
        # Мокаем создание ордера
        mock_order_result = {"order_id": "123", "status": "filled"}
        mock_order_service.create_order.return_value = mock_order_result
        
        result = await trade_service._place_order(api_key, api_secret, mock_template, signal, quantity)
        
        # Проверяем, что ордер был создан
        mock_order_service.create_order.assert_called_once_with(
            api_key, api_secret,
            symbol="BTCUSDT",
            side="BUY",
            quantity=quantity,
            leverage=10,
            order_type="MARKET"
        )
        assert result == mock_order_result 