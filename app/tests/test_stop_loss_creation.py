import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from services.deal_service import DealService
from services.trade_executor import TradeExecutor
from services.apikeys_service import APIKeysService
from services.strategy_log_service import StrategyLogService
from repositories.deal_repository import DealRepository
from clients.binance_client import BinanceClientFactory
from schemas.deal import DealCreate
from strategies.contracts import OrderIntent

# Мокируем модель Deal для тестов
class MockDeal:
    def __init__(self, id, user_id, symbol, side, entry_price, size, status, order_id=None, stop_loss_order_id=None, pnl=None, template_id=None, bot_id=None, stop_loss=None, opened_at: datetime = datetime.now(), closed_at: datetime = None):
        self.id = id
        self.user_id = user_id
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.size = size
        self.status = status
        self.order_id = order_id
        self.stop_loss_order_id = stop_loss_order_id
        self.pnl = pnl
        self.template_id = template_id
        self.bot_id = bot_id
        self.stop_loss = stop_loss
        self.opened_at = opened_at
        self.closed_at = closed_at


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)

@pytest.fixture
def mock_binance_client_factory():
    mock_factory = AsyncMock(spec=BinanceClientFactory)
    mock_client = AsyncMock()
    mock_factory.create.return_value = mock_client
    mock_factory.close.return_value = None
    return mock_factory, mock_client

@pytest.fixture
def mock_apikeys_service():
    mock_service = AsyncMock(spec=APIKeysService)
    mock_keys = MagicMock()
    mock_keys.api_key_encrypted = "test_api_key"
    mock_keys.api_secret_encrypted = "test_api_secret"
    mock_service.get_decrypted_by_user.return_value = [mock_keys]
    return mock_service

@pytest.fixture
def mock_deal_repository():
    mock_repo = AsyncMock(spec=DealRepository)
    mock_repo.add.side_effect = lambda **kwargs: MockDeal(id=1, **kwargs)
    mock_repo.update_stop_loss_order_id.return_value = None
    return mock_repo

@pytest.fixture
def mock_log_service():
    return AsyncMock(spec=StrategyLogService)

@pytest.fixture
def deal_service(mock_deal_repository, mock_binance_client_factory, mock_apikeys_service, mock_log_service):
    factory, _ = mock_binance_client_factory
    return DealService(
        repo=mock_deal_repository,
        binance_client=factory,
        apikeys_service=mock_apikeys_service,
        log_service=mock_log_service
    )

@pytest.fixture
def trade_executor(mock_binance_client_factory, mock_apikeys_service, mock_deal_repository, mock_log_service, deal_service):
    factory, _ = mock_binance_client_factory
    mock_balance_service = AsyncMock() # Не используется в _record_deal, мокаем
    mock_order_service = AsyncMock() # Не используется в _record_deal, мокаем
    mock_marketdata_service = AsyncMock() # Не используется в _record_deal, мокаем
    return TradeExecutor(
        exchange_client_factory=factory,
        balance_service=mock_balance_service,
        order_service=mock_order_service,
        deal_service=deal_service, # Используем реальный deal_service
        log_service=mock_log_service,
        apikeys_service=mock_apikeys_service,
        marketdata_service=mock_marketdata_service # Используем мок для MarketDataService
    )


@pytest.mark.asyncio
async def test_create_stop_loss_order_success(deal_service, mock_binance_client_factory, mock_session):
    _, mock_client = mock_binance_client_factory
    mock_client.futures_create_order.return_value = {"orderId": "SL_ORDER_123"}

    test_user_id = UUID("b795f441-2148-4388-bcfd-efcd6891e78f")
    test_deal = MockDeal(
        id=1,
        user_id=test_user_id,
        symbol="BTCUSDT",
        side="BUY",
        entry_price=100.0,
        size=0.001,
        status="open"
    )
    stop_loss_price = 99.0

    stop_loss_order_id = await deal_service.create_stop_loss_order(
        test_deal, mock_session, mock_client, stop_loss_price
    )

    mock_client.futures_create_order.assert_called_once_with(
        symbol="BTCUSDT",
        side="SELL", # BUY -> SELL
        type='STOP_MARKET',
        quantity=0.001,
        stopPrice=99.0,
        reduceOnly=True
    )
    deal_service.repo.update_stop_loss_order_id.assert_called_once_with(
        test_deal.id, "SL_ORDER_123", mock_session
    )
    mock_session.commit.assert_called_once()
    assert stop_loss_order_id == "SL_ORDER_123"


@pytest.mark.asyncio
async def test_create_stop_loss_order_exception(deal_service, mock_binance_client_factory, mock_session, capsys):
    _, mock_client = mock_binance_client_factory
    mock_client.futures_create_order.side_effect = Exception("Binance API Error")

    test_user_id = UUID("b795f441-2148-4388-bcfd-efcd6891e78f")
    test_deal = MockDeal(
        id=1,
        user_id=test_user_id,
        symbol="BTCUSDT",
        side="BUY",
        entry_price=100.0,
        size=0.001,
        status="open"
    )
    stop_loss_price = 99.0

    with pytest.raises(Exception, match="Binance API Error"):
        await deal_service.create_stop_loss_order(
            test_deal, mock_session, mock_client, stop_loss_price
        )
    
    captured = capsys.readouterr()
    assert "❌ Ошибка при создании стоп-лосс ордера на Binance: Binance API Error" in captured.out
    deal_service.repo.update_stop_loss_order_id.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_record_deal_with_stop_loss_creation(trade_executor, mock_binance_client_factory, mock_apikeys_service, mock_deal_repository, mock_session, mock_log_service):
    _, mock_client = mock_binance_client_factory
    mock_client.futures_create_order.return_value = {"orderId": "SL_ORDER_456"}
    
    # Мокируем _get_last_price и _calculate_quantity
    trade_executor._get_last_price = AsyncMock(return_value=100.0)
    trade_executor._calculate_quantity = AsyncMock(return_value=0.001)
    trade_executor._place_order = AsyncMock(return_value={"orderId": "MAIN_ORDER_123"})
    trade_executor._fetch_entry_price = AsyncMock(return_value=100.0)

    test_user_id = UUID("b795f441-2148-4388-bcfd-efcd6891e78f")
    test_bot_id = 1
    test_template = MagicMock()
    test_template.interval.value = "1m"
    test_template.strategy_config_id = 1 # Устанавливаем любое значение

    intent = OrderIntent(symbol="BTCUSDT", side="BUY", sizing="risk_pct", size=0.01, role="primary")

    # Мокируем стратегию для расчета стоп-лосса
    mock_strategy = MagicMock()
    mock_strategy.calculate_stop_loss_price.return_value = 99.0

    await trade_executor.execute_intent(
        intent=intent,
        template=test_template,
        user_id=test_user_id,
        bot_id=test_bot_id,
        api_key="test_api_key",
        api_secret="test_api_secret",
        session=mock_session,
        strategy=mock_strategy
    )

    # Проверяем, что create_stop_loss_order был вызван
    mock_deal_repository.add.assert_called_once() # Проверяем, что сделка добавлена
    mock_deal_repository.update_stop_loss_order_id.assert_called_once_with(
        1, "SL_ORDER_456", mock_session
    )
    mock_log_service.add_log.assert_called_once() # Проверяем, что лог добавлен
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_record_deal_no_stop_loss_price(trade_executor, mock_binance_client_factory, mock_apikeys_service, mock_deal_repository, mock_session, mock_log_service, capsys):
    _, mock_client = mock_binance_client_factory
    mock_client.futures_create_order.return_value = {"orderId": "SL_ORDER_789"} # Должен быть вызван fallback

    trade_executor._get_last_price = AsyncMock(return_value=100.0)
    trade_executor._calculate_quantity = AsyncMock(return_value=0.001)
    trade_executor._place_order = AsyncMock(return_value={"orderId": "MAIN_ORDER_123"})
    trade_executor._fetch_entry_price = AsyncMock(return_value=100.0)

    test_user_id = UUID("b795f441-2148-4388-bcfd-efcd6891e78f")
    test_bot_id = 1
    test_template = MagicMock()
    test_template.interval.value = "1m"
    test_template.strategy_config_id = 1

    intent = OrderIntent(symbol="BTCUSDT", side="BUY", sizing="risk_pct", size=0.01, role="primary")

    # Мокируем стратегию так, чтобы она НЕ возвращала stop_loss_price
    mock_strategy = MagicMock()
    mock_strategy.calculate_stop_loss_price.return_value = None # Важно!

    await trade_executor.execute_intent(
        intent=intent,
        template=test_template,
        user_id=test_user_id,
        bot_id=test_bot_id,
        api_key="test_api_key",
        api_secret="test_api_secret",
        session=mock_session,
        strategy=mock_strategy
    )
    
    captured = capsys.readouterr()
    assert "⚠️ Стоп-лосс не рассчитан стратегией." in captured.out
    mock_client.futures_create_order.assert_not_called()
    mock_log_service.add_log.assert_called_once()

    # Проверяем, что stop_loss в созданной сделке равен None
    add_kwargs = mock_deal_repository.add.call_args[1]
    assert add_kwargs['stop_loss'] is None


@pytest.mark.asyncio
async def test_record_deal_no_apikeys(trade_executor, mock_binance_client_factory, mock_apikeys_service, mock_deal_repository, mock_session, mock_log_service, capsys):
    mock_apikeys_service.get_decrypted_by_user.return_value = [] # Нет ключей

    trade_executor._get_last_price = AsyncMock(return_value=100.0)
    trade_executor._calculate_quantity = AsyncMock(return_value=0.001)
    trade_executor._place_order = AsyncMock(return_value={"orderId": "MAIN_ORDER_123"})
    trade_executor._fetch_entry_price = AsyncMock(return_value=100.0)

    test_user_id = UUID("b795f441-2148-4388-bcfd-efcd6891e78f")
    test_bot_id = 1
    test_template = MagicMock()
    test_template.interval.value = "1m"
    test_template.strategy_config_id = 1

    intent = OrderIntent(symbol="BTCUSDT", side="BUY", sizing="risk_pct", size=0.01, role="primary")

    mock_strategy = MagicMock()
    mock_strategy.calculate_stop_loss_price.return_value = 99.0

    await trade_executor.execute_intent(
        intent=intent,
        template=test_template,
        user_id=test_user_id,
        bot_id=test_bot_id,
        api_key="test_api_key",
        api_secret="test_api_secret",
        session=mock_session,
        strategy=mock_strategy
    )
    
    captured = capsys.readouterr()
    assert "❌ Не удалось получить API ключи для создания стоп-лосс ордера" in captured.out
    mock_deal_repository.update_stop_loss_order_id.assert_not_called() # Не должен вызываться
    mock_session.commit.assert_not_called() # Не должен быть коммит, так как нет SL ордера
