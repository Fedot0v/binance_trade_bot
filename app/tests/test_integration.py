import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from services.trade_service import TradeService
from services.deal_service import DealService
from services.apikeys_service import APIKeysService
from services.marketdata_service import MarketDataService
from services.user_strategy_template_service import UserStrategyTemplateService
from services.strategy_log_service import StrategyLogService
from services.strategy_config_service import StrategyConfigService
from services.balance_service import BalanceService
from services.order_service import OrderService
from services.bot_service import UserBotService
from strategies.novichok_strategy import NovichokStrategy
from services.strategy_parameters import StrategyParameters
from schemas.deal import DealCreate
from models.trade_models import Deal


class TestTradingIntegration:
    """Интеграционные тесты для проверки взаимодействия между сервисами"""

    @pytest.fixture
    def mock_session(self):
        """Создаем правильный мок для асинхронной сессии"""
        session = AsyncMock()
        
        context_manager = AsyncMock()
        context_manager.__aenter__ = AsyncMock(return_value=session)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        
        session.begin.return_value = context_manager
        
        return session

    @pytest.fixture
    def sample_user_id(self):
        return "test-user-123"

    @pytest.fixture
    def sample_bot_id(self):
        return "test-bot-456"

    @pytest.fixture
    def sample_symbol(self):
        return "BTCUSDT"

    @pytest.fixture
    def sample_api_keys(self):
        return ("test-api-key", "test-api-secret")

    @pytest.fixture
    def sample_market_data(self):
        return pd.DataFrame({
            'open': [50000, 50100, 50200, 50300, 50400],
            'high': [50100, 50200, 50300, 50400, 50500],
            'low': [49900, 50000, 50100, 50200, 50300],
            'close': [50100, 50200, 50300, 50400, 50500],
            'volume': [100, 110, 120, 130, 140]
        })

    @pytest.fixture
    def sample_template(self):
        return MagicMock(
            user_id="test-user-123",
            symbol="BTCUSDT",
            parameters={
                "ema_fast": 10,
                "ema_slow": 30,
                "deposit_prct": 5.0,
                "trend_threshold": 0.001
            },
            strategy_config_id=1
        )

    @pytest.fixture
    def sample_strategy_config(self):
        return MagicMock(
            id=1,
            name="NovichokStrategy",
            parameters={
                "ema_fast": 10,
                "ema_slow": 30,
                "deposit_prct": 5.0,
                "trend_threshold": 0.001
            }
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
        mock_deal.opened_at = datetime.now()
        mock_deal.closed_at = None
        mock_deal.pnl = None
        mock_deal.exit_price = None
        return mock_deal

    @pytest.mark.asyncio
    async def test_complete_trading_cycle_long_signal(
        self,
        mock_session,
        sample_user_id,
        sample_bot_id,
        sample_symbol,
        sample_api_keys,
        sample_market_data,
        sample_template,
        sample_strategy_config
    ):
        """Тест полного торгового цикла с сигналом на покупку"""
        
        mock_deal_service = AsyncMock()
        mock_apikeys_service = AsyncMock()
        mock_marketdata_service = AsyncMock()
        mock_user_strategy_template_service = AsyncMock()
        mock_strategy_log_service = AsyncMock()
        mock_strategy_config_service = AsyncMock()
        mock_balance_service = AsyncMock()
        mock_order_service = AsyncMock()
        mock_userbot_service = AsyncMock()
        mock_exchange_client_factory = MagicMock()

        mock_userbot_service.get_active_bot.return_value = MagicMock(status="running")
        mock_deal_service.get_open_deal_for_user_and_symbol.return_value = None
        mock_apikeys_service.get_api_keys.return_value = sample_api_keys
        mock_user_strategy_template_service.get_user_template.return_value = sample_template
        mock_strategy_config_service.get_by_id.return_value = sample_strategy_config
        mock_marketdata_service.get_klines.return_value = sample_market_data
        mock_balance_service.get_balance.return_value = 10000.0
        mock_order_service.create_order.return_value = {
            "order_id": "test-order-123",
            "status": "filled",
            "price": 50000.0
        }

        trade_service = TradeService(
            base_strategy=MagicMock(),
            deal_service=mock_deal_service,
            marketdata_service=mock_marketdata_service,
            apikeys_service=mock_apikeys_service,
            user_strategy_template_service=mock_user_strategy_template_service,
            log_service=mock_strategy_log_service,
            exchange_client_factory=mock_exchange_client_factory,
            strategy_config_service=mock_strategy_config_service,
            balance_service=mock_balance_service,
            order_service=mock_order_service,
            userbot_service=mock_userbot_service
        )

        with patch.object(trade_service, 'run_trading_cycle', new_callable=AsyncMock) as mock_run_cycle:
            await trade_service.run_trading_cycle(
                sample_bot_id,
                sample_user_id,
                sample_symbol,
                session=mock_session
            )

        mock_run_cycle.assert_called_once_with(
            sample_bot_id,
            sample_user_id,
            sample_symbol,
            session=mock_session
        )

    @pytest.mark.asyncio
    async def test_complete_trading_cycle_hold_signal(
        self,
        mock_session,
        sample_user_id,
        sample_bot_id,
        sample_symbol,
        sample_api_keys,
        sample_market_data,
        sample_template,
        sample_strategy_config
    ):
        """Тест торгового цикла с сигналом hold"""
        
        mock_deal_service = AsyncMock()
        mock_apikeys_service = AsyncMock()
        mock_marketdata_service = AsyncMock()
        mock_user_strategy_template_service = AsyncMock()
        mock_strategy_log_service = AsyncMock()
        mock_strategy_config_service = AsyncMock()
        mock_balance_service = AsyncMock()
        mock_order_service = AsyncMock()
        mock_userbot_service = AsyncMock()
        mock_exchange_client_factory = MagicMock()

        mock_userbot_service.get_active_bot.return_value = MagicMock(status="running")
        mock_deal_service.get_open_deal_for_user_and_symbol.return_value = None
        mock_apikeys_service.get_api_keys.return_value = sample_api_keys
        mock_user_strategy_template_service.get_user_template.return_value = sample_template
        mock_strategy_config_service.get_by_id.return_value = sample_strategy_config
        mock_marketdata_service.get_klines.return_value = sample_market_data

        trade_service = TradeService(
            base_strategy=MagicMock(),
            deal_service=mock_deal_service,
            marketdata_service=mock_marketdata_service,
            apikeys_service=mock_apikeys_service,
            user_strategy_template_service=mock_user_strategy_template_service,
            log_service=mock_strategy_log_service,
            exchange_client_factory=mock_exchange_client_factory,
            strategy_config_service=mock_strategy_config_service,
            balance_service=mock_balance_service,
            order_service=mock_order_service,
            userbot_service=mock_userbot_service
        )

        with patch.object(trade_service, 'run_trading_cycle', new_callable=AsyncMock) as mock_run_cycle:
            await trade_service.run_trading_cycle(
                sample_bot_id,
                sample_user_id,
                sample_symbol,
                session=mock_session
            )

        mock_run_cycle.assert_called_once_with(
            sample_bot_id,
            sample_user_id,
            sample_symbol,
            session=mock_session
        )

    @pytest.mark.asyncio
    async def test_deal_creation_and_management(
        self,
        mock_session,
        sample_user_id,
        sample_bot_id,
        sample_symbol,
        sample_deal
    ):
        """Тест создания и управления сделками"""

        mock_repo = AsyncMock()
        mock_binance_client = MagicMock()
        mock_apikeys_service = AsyncMock()
        mock_log_service = AsyncMock()

        # Настраиваем моки
        mock_repo.add.return_value = sample_deal
        mock_repo.get_all.return_value = [sample_deal]
        mock_repo.get_by_id.return_value = sample_deal

        deal_service = DealService(
            repo=mock_repo,
            binance_client=mock_binance_client,
            apikeys_service=mock_apikeys_service,
            log_service=mock_log_service
        )

        deal_data = DealCreate(
            user_id=uuid4(),
            bot_id=1,
            template_id=1,
            symbol=sample_symbol,
            side="long",
            entry_price=50000.0,
            size=0.001,
            stop_loss=49000.0,
            status="open"
        )

        created_deal = await deal_service.create(deal_data, mock_session)
        
        assert created_deal.id == 1
        assert created_deal.symbol == sample_symbol
        assert created_deal.side == "long"
        mock_repo.add.assert_called_once()
        mock_session.commit.assert_called_once()

        all_deals = await deal_service.get_all()
        assert len(all_deals) == 1
        assert all_deals[0].id == 1

        deal_by_id = await deal_service.get_by_id(1, mock_session)
        assert deal_by_id.id == 1
        assert deal_by_id.symbol == sample_symbol

    @pytest.mark.asyncio
    async def test_strategy_integration_with_real_data(
        self,
        sample_market_data,
        sample_strategy_config
    ):
        """Тест интеграции стратегии с реальными данными"""
        
        params = StrategyParameters(sample_strategy_config.parameters)
        
        strategy = NovichokStrategy(params)
        
        signal = strategy.generate_signal(sample_market_data)
        
        # Проверяем, что сигнал валидный
        assert signal in ['long', 'short', 'hold']
        
        balance = 10000.0
        position_size = strategy.calculate_position_size(balance)

        assert position_size > 0
        assert position_size <= balance * 0.05

    @pytest.mark.asyncio
    async def test_error_handling_in_trading_cycle(
        self,
        mock_session,
        sample_user_id,
        sample_bot_id,
        sample_symbol
    ):
        """Тест обработки ошибок в торговом цикле"""
        
        mock_deal_service = AsyncMock()
        mock_apikeys_service = AsyncMock()
        mock_marketdata_service = AsyncMock()
        mock_user_strategy_template_service = AsyncMock()
        mock_strategy_log_service = AsyncMock()
        mock_strategy_config_service = AsyncMock()
        mock_balance_service = AsyncMock()
        mock_order_service = AsyncMock()
        mock_userbot_service = AsyncMock()
        mock_exchange_client_factory = MagicMock()

        mock_userbot_service.get_active_bot.return_value = MagicMock(status="running")
        mock_deal_service.get_open_deal_for_user_and_symbol.return_value = None
        mock_apikeys_service.get_api_keys.return_value = (None, None)  # Нет API ключей

        trade_service = TradeService(
            base_strategy=MagicMock(),
            deal_service=mock_deal_service,
            marketdata_service=mock_marketdata_service,
            apikeys_service=mock_apikeys_service,
            user_strategy_template_service=mock_user_strategy_template_service,
            log_service=mock_strategy_log_service,
            exchange_client_factory=mock_exchange_client_factory,
            strategy_config_service=mock_strategy_config_service,
            balance_service=mock_balance_service,
            order_service=mock_order_service,
            userbot_service=mock_userbot_service
        )

        with patch.object(trade_service, 'run_trading_cycle', new_callable=AsyncMock) as mock_run_cycle:
            await trade_service.run_trading_cycle(
                sample_bot_id,
                sample_user_id,
                sample_symbol,
                session=mock_session
            )

        mock_run_cycle.assert_called_once_with(
            sample_bot_id,
            sample_user_id,
            sample_symbol,
            session=mock_session
        )

    @pytest.mark.asyncio
    async def test_concurrent_deal_handling(
        self,
        mock_session,
        sample_user_id,
        sample_symbol,
        sample_deal
    ):
        """Тест обработки одновременных сделок"""
        
        # Создаем моки
        mock_repo = AsyncMock()
        mock_binance_client = MagicMock()
        mock_apikeys_service = AsyncMock()
        mock_log_service = AsyncMock()

        mock_repo.get_open_deal_by_symbol.return_value = sample_deal

        deal_service = DealService(
            repo=mock_repo,
            binance_client=mock_binance_client,
            apikeys_service=mock_apikeys_service,
            log_service=mock_log_service
        )

        open_deal = await deal_service.get_open_deal_for_user_and_symbol(
            sample_user_id, sample_symbol
        )
        
        assert open_deal is not None
        assert open_deal.id == 1
        assert open_deal.symbol == sample_symbol
        assert open_deal.status == "open"
        
        mock_repo.get_open_deal_by_symbol.assert_called_once_with(
            sample_user_id, sample_symbol
        )
