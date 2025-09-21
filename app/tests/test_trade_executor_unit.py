import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from strategies.contracts import OrderIntent
from services.trade.trade_executor import TradeExecutor


@pytest.mark.asyncio
async def test_execute_intent_places_order_and_records_deal():
    # Зависимости TradeExecutor
    exchange_client_factory = AsyncMock()
    balance_service = AsyncMock()
    order_service = AsyncMock()
    deal_service = AsyncMock()
    log_service = AsyncMock()
    apikeys_service = AsyncMock()
    marketdata_service = AsyncMock()

    # Входные данные
    template = MagicMock(id=1, leverage=10, interval=MagicMock(value="1m"))
    user_id = uuid4()
    bot_id = 1
    api_key = "k"
    api_secret = "s"
    session = MagicMock()

    # Маркет-данные для _get_last_price
    marketdata_service.get_klines = AsyncMock(return_value=[[0, "100.0", 0, 0, "100.0", 0, 0, 0, 0, 0, 0, 0]])

    # Баланс и ордера
    balance_service.get_futures_balance = AsyncMock(return_value={"available": 1000.0})
    order_service.create_order = AsyncMock(return_value={"orderId": "order-1", "status": "FILLED"})

    # Клиент биржи для получения цены входа
    client = AsyncMock()
    client.futures_get_order = AsyncMock(return_value={
        "avgPrice": "100.0",
        "executedQty": "0.5",
        "cumQuote": "50"
    })
    exchange_client_factory.create = AsyncMock(return_value=client)
    exchange_client_factory.close = AsyncMock(return_value=None)

    # Создание сделки и стоп-лосса
    deal_service.create = AsyncMock(return_value=MagicMock(id=123, size=0.5))
    deal_service.create_stop_loss_order = AsyncMock(return_value="sl-1")
    apikeys_service.get_decrypted_by_user = AsyncMock(return_value=[MagicMock(api_key_encrypted="k", api_secret_encrypted="s")])

    # Стратегия возвращает цену стоп-лосса
    class StrategyStub:
        def calculate_stop_loss_price(self, entry_price: float, side: str, symbol: str) -> float:
            return entry_price * (0.98 if side == 'long' else 1.02)

    strategy = StrategyStub()

    executor = TradeExecutor(
        exchange_client_factory=exchange_client_factory,
        balance_service=balance_service,
        order_service=order_service,
        deal_service=deal_service,
        log_service=log_service,
        apikeys_service=apikeys_service,
        marketdata_service=marketdata_service
    )

    # Intent c размером в процентах от баланса
    intent = OrderIntent(symbol="BTCUSDT", side="BUY", sizing="risk_pct", size=0.05, role="primary")

    await executor.execute_intent(
        intent=intent,
        template=template,
        user_id=user_id,
        bot_id=bot_id,
        api_key=api_key,
        api_secret=api_secret,
        session=session,
        strategy=strategy,
    )

    # Проверяем, что ордер создан, сделка записана и стоп-лосс выставлен
    order_service.create_order.assert_awaited()
    deal_service.create.assert_awaited()
    deal_service.create_stop_loss_order.assert_awaited()

    # Проверяем количество и параметры ордера (0.05 * 1000 / 100 = 0.5)
    assert order_service.create_order.await_args.kwargs["quantity"] == pytest.approx(0.5, rel=1e-6)


@pytest.mark.asyncio
async def test_execute_intent_raises_when_no_market_data():
    exchange_client_factory = AsyncMock()
    balance_service = AsyncMock()
    order_service = AsyncMock()
    deal_service = AsyncMock()
    log_service = AsyncMock()
    apikeys_service = AsyncMock()
    marketdata_service = AsyncMock()

    marketdata_service.get_klines = AsyncMock(return_value=[])

    executor = TradeExecutor(
        exchange_client_factory=exchange_client_factory,
        balance_service=balance_service,
        order_service=order_service,
        deal_service=deal_service,
        log_service=log_service,
        apikeys_service=apikeys_service,
        marketdata_service=marketdata_service
    )

    template = MagicMock(id=1, leverage=10, interval=MagicMock(value="1m"))
    intent = OrderIntent(symbol="BTCUSDT", side="BUY", sizing="risk_pct", size=0.05, role="primary")

    with pytest.raises(ValueError):
        await executor.execute_intent(
            intent=intent,
            template=template,
            user_id="user",
            bot_id="bot",
            api_key="k",
            api_secret="s",
            session=MagicMock(),
        )


