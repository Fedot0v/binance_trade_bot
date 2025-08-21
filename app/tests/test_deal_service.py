import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from datetime import datetime
from uuid import uuid4

from services.deal_service import DealService
from schemas.deal import DealCreate, DealRead, DealDelete
from models.trade_models import Deal


class TestDealService:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_binance_client(self):
        return MagicMock()

    @pytest.fixture
    def mock_apikeys_service(self):
        return AsyncMock()

    @pytest.fixture
    def mock_log_service(self):
        return AsyncMock()

    @pytest.fixture
    def mock_strategy_config_service(self):
        return AsyncMock()

    @pytest.fixture
    def deal_service(self, mock_repo, mock_binance_client, mock_apikeys_service, mock_log_service, mock_strategy_config_service):
        service = DealService(
            repo=mock_repo,
            binance_client=mock_binance_client,
            apikeys_service=mock_apikeys_service,
            log_service=mock_log_service,
            strategy_config_service=mock_strategy_config_service
        )
        # Мокаем метод получения названия стратегии
        service._get_strategy_name = AsyncMock(return_value="TestStrategy")
        return service

    @pytest.fixture
    def sample_deal_data(self):
        return DealCreate(
            user_id=uuid4(),
            bot_id=1,
            template_id=1,
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            size=0.001,
            stop_loss=49000.0,
            status="open"
        )

    @pytest.fixture
    def sample_deal_model(self):
        """Создаем мок модели Deal вместо реальной"""
        mock_deal = MagicMock()
        mock_deal.id = 1
        mock_deal.user_id = uuid4()
        mock_deal.bot_id = 1
        mock_deal.template_id = 1
        mock_deal.symbol = "BTCUSDT"
        mock_deal.side = "BUY"
        mock_deal.entry_price = 50000.0
        mock_deal.size = 0.001
        mock_deal.stop_loss = 49000.0
        mock_deal.status = "open"
        mock_deal.opened_at = datetime.now()
        mock_deal.closed_at = None
        mock_deal.pnl = None
        mock_deal.exit_price = None
        mock_deal.order_id = None
        mock_deal.stop_loss_order_id = None
        return mock_deal

    @pytest.mark.asyncio
    async def test_create_deal_success(self, deal_service, mock_repo, sample_deal_data, sample_deal_model):
        # Arrange
        mock_session = AsyncMock()
        mock_repo.add.return_value = sample_deal_model

        # Act
        result = await deal_service.create(sample_deal_data, mock_session)

        # Assert
        assert isinstance(result, DealRead)
        assert result.id == 1
        assert result.symbol == "BTCUSDT"
        assert result.side == "BUY"
        mock_repo.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_deal_without_autocommit(self, deal_service, mock_repo, sample_deal_data, sample_deal_model):
        # Arrange
        mock_session = AsyncMock()
        mock_repo.add.return_value = sample_deal_model

        # Act
        result = await deal_service.create(sample_deal_data, mock_session, autocommit=False)

        # Assert
        assert isinstance(result, DealRead)
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_all_deals(self, deal_service, mock_repo, sample_deal_model):
        # Arrange
        mock_repo.get_all.return_value = [sample_deal_model]

        # Act
        result = await deal_service.get_all()

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], DealRead)
        assert result[0].id == 1
        mock_repo.get_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_deals_empty(self, deal_service, mock_repo):
        # Arrange
        mock_repo.get_all.return_value = []

        # Act
        result = await deal_service.get_all()

        # Assert
        assert len(result) == 0
        mock_repo.get_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_deal_success(self, deal_service, mock_repo):
        # Arrange
        mock_session = AsyncMock()
        deal_id = 1

        # Act
        result = await deal_service.delete_by_id(deal_id, mock_session)

        # Assert
        assert isinstance(result, DealDelete)
        assert result.id == deal_id
        assert "успешно удалена" in result.message
        mock_repo.delete_deal.assert_called_once_with(deal_id, mock_session)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_deal_by_id_success(self, deal_service, mock_repo, sample_deal_model):
        # Arrange
        mock_session = AsyncMock()
        deal_id = 1
        mock_repo.get_by_id.return_value = sample_deal_model

        # Act
        result = await deal_service.get_by_id(deal_id, mock_session)

        # Assert
        assert isinstance(result, DealRead)
        assert result.id == deal_id
        mock_repo.get_by_id.assert_called_once_with(deal_id, mock_session)

    @pytest.mark.asyncio
    async def test_get_deal_by_id_not_found(self, deal_service, mock_repo):
        # Arrange
        mock_session = AsyncMock()
        deal_id = 999
        mock_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await deal_service.get_by_id(deal_id, mock_session)
        
        assert exc_info.value.status_code == 404
        assert f"Сделка с ID {deal_id} не найдена" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_open_deal_for_user_and_symbol_found(self, deal_service, mock_repo, sample_deal_model):
        # Arrange
        user_id = uuid4()
        symbol = "BTCUSDT"
        mock_repo.get_open_deal_by_symbol.return_value = sample_deal_model

        # Act
        result = await deal_service.get_open_deal_for_user_and_symbol(user_id, symbol)

        # Assert
        assert result == sample_deal_model
        mock_repo.get_open_deal_by_symbol.assert_called_once_with(user_id, symbol)

    @pytest.mark.asyncio
    async def test_get_open_deal_for_user_and_symbol_not_found(self, deal_service, mock_repo):
        # Arrange
        user_id = uuid4()
        symbol = "BTCUSDT"
        mock_repo.get_open_deal_by_symbol.return_value = None

        # Act
        result = await deal_service.get_open_deal_for_user_and_symbol(user_id, symbol)

        # Assert
        assert result is None
        mock_repo.get_open_deal_by_symbol.assert_called_once_with(user_id, symbol)

    @pytest.mark.asyncio
    async def test_close_deal_success(self, deal_service, mock_repo):
        # Arrange
        mock_session = AsyncMock()
        deal_id = 1
        exit_price = 51000.0
        pnl = 100.0

        # Act
        await deal_service.close(deal_id, exit_price, pnl, mock_session)

        # Assert
        mock_repo.close_deal.assert_called_once_with(
            deal_id, 
            exit_price=exit_price, 
            pnl=pnl, 
            session=mock_session
        )
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_open_deals(self, deal_service, mock_repo, sample_deal_model):
        # Arrange
        mock_session = AsyncMock()
        mock_repo.get_open_deals.return_value = [sample_deal_model]

        # Act
        result = await deal_service.get_all_open_deals(mock_session)

        # Assert
        assert len(result) == 1
        assert result[0] == sample_deal_model
        mock_repo.get_open_deals.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_watcher_cycle_no_open_deals(self, deal_service, mock_repo):
        # Arrange
        mock_session = AsyncMock()
        mock_repo.get_open_deals.return_value = []

        # Act
        await deal_service.watcher_cycle(mock_session)

        # Assert
        mock_repo.get_open_deals.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_watcher_cycle_with_open_deals(self, deal_service, mock_repo, sample_deal_model):
        # Arrange
        mock_session = AsyncMock()
        mock_repo.get_open_deals.return_value = [sample_deal_model]
        
        # Mock the _process_open_deal method
        with patch.object(deal_service, '_process_open_deal', new_callable=AsyncMock) as mock_process:
            # Act
            await deal_service.watcher_cycle(mock_session)

            # Assert
            mock_repo.get_open_deals.assert_called_once_with(mock_session)
            mock_process.assert_called_once_with(sample_deal_model, mock_session) 

    @pytest.mark.asyncio
    async def test_create_stop_loss_order_success(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Мокаем ответ от Binance
        mock_order_response = {"orderId": "12345"}
        mock_client.futures_create_order.return_value = mock_order_response
        
        # Мокаем репозиторий
        deal_service.repo = AsyncMock()
        
        # Act
        result = await deal_service.create_stop_loss_order(
            sample_deal_model, mock_session, mock_client, 49000.0
        )
        
        # Assert
        assert result == "12345"
        # Проверяем, что ордер создан с правильными параметрами
        mock_client.futures_create_order.assert_called_once()
        call_args = mock_client.futures_create_order.call_args
        assert call_args.kwargs['symbol'] == "BTCUSDT"
        assert call_args.kwargs['type'] == "STOP_MARKET"
        assert call_args.kwargs['quantity'] == 0.001
        assert call_args.kwargs['stopPrice'] == 49000.0
        assert call_args.kwargs['reduceOnly'] == True
        
        deal_service.repo.update_stop_loss_order_id.assert_called_once_with(1, "12345", mock_session)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_stop_loss_order_for_short(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Меняем сторону на шорт
        sample_deal_model.side = "SELL"
        
        # Мокаем ответ от Binance
        mock_order_response = {"orderId": "67890"}
        mock_client.futures_create_order.return_value = mock_order_response
        
        # Мокаем репозиторий
        deal_service.repo = AsyncMock()
        
        # Act
        result = await deal_service.create_stop_loss_order(
            sample_deal_model, mock_session, mock_client, 51000.0
        )
        
        # Assert
        assert result == "67890"
        # Проверяем, что ордер создан с правильными параметрами
        mock_client.futures_create_order.assert_called_once()
        call_args = mock_client.futures_create_order.call_args
        assert call_args.kwargs['symbol'] == "BTCUSDT"
        assert call_args.kwargs['type'] == "STOP_MARKET"
        assert call_args.kwargs['quantity'] == 0.001
        assert call_args.kwargs['stopPrice'] == 51000.0
        assert call_args.kwargs['reduceOnly'] == True
        
        deal_service.repo.update_stop_loss_order_id.assert_called_once_with(1, "67890", mock_session)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stop_loss_order_success(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Добавляем существующий stop_loss_order_id
        sample_deal_model.stop_loss_order_id = "12345"
        
        # Мокаем ответы от Binance
        mock_new_order_response = {"orderId": "67890"}
        mock_client.futures_create_order.return_value = mock_new_order_response
        
        # Мокаем репозиторий
        deal_service.repo = AsyncMock()
        
        # Act
        result = await deal_service.update_stop_loss_order(
            sample_deal_model, mock_session, mock_client, 48500.0
        )
        
        # Assert
        assert result == "67890"
        # Проверяем, что старый ордер был отменен
        mock_client.futures_cancel_order.assert_called_once_with(
            symbol="BTCUSDT",
            orderId=12345
        )
        # Проверяем, что новый ордер создан
        mock_client.futures_create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stop_loss_order_without_existing(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Убираем существующий stop_loss_order_id
        sample_deal_model.stop_loss_order_id = None
        
        # Мокаем ответ от Binance
        mock_order_response = {"orderId": "67890"}
        mock_client.futures_create_order.return_value = mock_order_response
        
        # Мокаем репозиторий
        deal_service.repo = AsyncMock()
        
        # Act
        result = await deal_service.update_stop_loss_order(
            sample_deal_model, mock_session, mock_client, 48500.0
        )
        
        # Assert
        assert result == "67890"
        # Проверяем, что отмена не вызывалась
        mock_client.futures_cancel_order.assert_not_called()
        # Проверяем, что новый ордер создан
        mock_client.futures_create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_stop_loss_order_success(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Добавляем существующий stop_loss_order_id
        sample_deal_model.stop_loss_order_id = "12345"
        
        # Мокаем репозиторий
        deal_service.repo = AsyncMock()
        
        # Act
        await deal_service.cancel_stop_loss_order(
            sample_deal_model, mock_session, mock_client
        )
        
        # Assert
        mock_client.futures_cancel_order.assert_called_once_with(
            symbol="BTCUSDT",
            orderId=12345
        )
        deal_service.repo.update_stop_loss_order_id.assert_called_once_with(1, None, mock_session)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_stop_loss_order_without_existing(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Убираем существующий stop_loss_order_id
        sample_deal_model.stop_loss_order_id = None
        
        # Мокаем репозиторий
        deal_service.repo = AsyncMock()
        
        # Act
        await deal_service.cancel_stop_loss_order(
            sample_deal_model, mock_session, mock_client
        )
        
        # Assert
        # Проверяем, что отмена не вызывалась
        mock_client.futures_cancel_order.assert_not_called()
        deal_service.repo.update_stop_loss_order_id.assert_not_called()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_stop_loss_order_status_filled(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Добавляем stop_loss_order_id
        sample_deal_model.stop_loss_order_id = "12345"
        
        # Мокаем ответ от Binance - ордер исполнен
        mock_order_info = {
            'status': 'FILLED',
            'avgPrice': '49000.0',
            'executedQty': '0.001'
        }
        mock_client.futures_get_order.return_value = mock_order_info
        
        # Мокаем репозиторий и log_service
        deal_service.repo = AsyncMock()
        deal_service.log_service = AsyncMock()
        
        # Act
        result = await deal_service.check_stop_loss_order_status(
            sample_deal_model, mock_session, mock_client
        )
        
        # Assert
        assert result == True
        mock_client.futures_get_order.assert_called_once_with(
            symbol="BTCUSDT",
            orderId=12345
        )
        # Проверяем, что сделка закрыта
        deal_service.repo.close_deal.assert_called_once()
        deal_service.log_service.add_log.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_stop_loss_order_status_new(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Добавляем stop_loss_order_id
        sample_deal_model.stop_loss_order_id = "12345"
        
        # Мокаем ответ от Binance - ордер еще активен
        mock_order_info = {
            'status': 'NEW',
            'avgPrice': '0',
            'executedQty': '0'
        }
        mock_client.futures_get_order.return_value = mock_order_info
        
        # Мокаем репозиторий
        deal_service.repo = AsyncMock()
        
        # Act
        result = await deal_service.check_stop_loss_order_status(
            sample_deal_model, mock_session, mock_client
        )
        
        # Assert
        assert result == False
        # Проверяем, что сделка НЕ закрыта
        deal_service.repo.close_deal.assert_not_called()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_stop_loss_order_status_canceled(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_binance_client.create.return_value = mock_client
        
        # Добавляем stop_loss_order_id
        sample_deal_model.stop_loss_order_id = "12345"
        
        # Мокаем ответ от Binance - ордер отменен
        mock_order_info = {
            'status': 'CANCELED',
            'avgPrice': '0',
            'executedQty': '0'
        }
        mock_client.futures_get_order.return_value = mock_order_info
        
        # Мокаем репозиторий
        deal_service.repo = AsyncMock()
        
        # Act
        result = await deal_service.check_stop_loss_order_status(
            sample_deal_model, mock_session, mock_client
        )
        
        # Assert
        assert result == False
        # Проверяем, что ID ордера очищен
        deal_service.repo.update_stop_loss_order_id.assert_called_once_with(1, None, mock_session)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_stop_loss_order_status_without_order_id(self, deal_service, sample_deal_model, mock_binance_client):
        # Arrange
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        
        # Убираем stop_loss_order_id
        sample_deal_model.stop_loss_order_id = None
        
        # Act
        result = await deal_service.check_stop_loss_order_status(
            sample_deal_model, mock_session, mock_client
        )
        
        # Assert
        assert result == False
        # Проверяем, что запрос к Binance не делался
        mock_client.futures_get_order.assert_not_called() 