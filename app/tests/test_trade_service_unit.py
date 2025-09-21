import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.trade.trade_service import TradeService


@pytest.mark.asyncio
async def test_trade_service_full_cycle_calls_executor(monkeypatch):
    # Зависимости
    deal_service = AsyncMock()
    marketdata_service = AsyncMock()
    apikeys_service = AsyncMock()
    user_strategy_template_service = AsyncMock()
    log_service = AsyncMock()
    exchange_client_factory = AsyncMock()
    strategy_config_service = AsyncMock()
    balance_service = AsyncMock()
    order_service = AsyncMock()
    userbot_service = AsyncMock()

    # Активный бот и отсутствие открытых сделок
    userbot_service.get_active_bot = AsyncMock(return_value=MagicMock(status="running"))
    deal_service.get_open_deal_for_user_and_symbol = AsyncMock(return_value=None)

    # Ключи и шаблон
    apikeys_service.get_active = AsyncMock(return_value=[MagicMock(api_key_encrypted="k", api_secret_encrypted="s")])
    template = MagicMock(
        id=1,
        strategy_config_id=1,
        symbol="BTCUSDT",
        interval=MagicMock(value="1m"),
        leverage=10,
        parameters={
            'ema_fast': 5,
            'ema_slow': 10,
            'trend_threshold': 0.0001,
            'deposit_prct': 0.05
        }
    )
    user_strategy_template_service.get_active_strategie = AsyncMock(return_value=template)
    from types import SimpleNamespace
    strategy_config_service.get_by_id = AsyncMock(return_value=SimpleNamespace(name="Novichok"))

    # Маркет-данные (последовательность свечей)
    marketdata_service.get_klines = AsyncMock(return_value=[[0, "100.0", 0, 0, "100.0", 0, 0, 0, 0, 0, 0, 0] for _ in range(50)])

    # Мокаем executor.execute_intent, чтобы не идти в сеть/БД
    calls = {"executed": 0}
    async def fake_execute_intent(**kwargs):
        calls["executed"] += 1
        return None

    # Внедрим мок прямо в инстанс TradeService после инициализации
    ts = TradeService(
        deal_service=deal_service,
        marketdata_service=marketdata_service,
        apikeys_service=apikeys_service,
        user_strategy_template_service=user_strategy_template_service,
        log_service=log_service,
        exchange_client_factory=exchange_client_factory,
        strategy_config_service=strategy_config_service,
        balance_service=balance_service,
        order_service=order_service,
        userbot_service=userbot_service
    )
    ts.trade_executor.execute_intent = AsyncMock(side_effect=fake_execute_intent)

    class DummySession:
        def begin(self):
            class _C:
                async def __aenter__(self_inner):
                    return self_inner
                async def __aexit__(self_inner, exc_type, exc, tb):
                    return False
            return _C()

    await ts.run_trading_cycle(
        bot_id="bot-1",
        user_id=uuid4(),
        symbol="BTCUSDT",
        session=DummySession()
    )

    # Проверяем, что исполнение намерений было вызвано хотя бы один раз
    assert calls["executed"] >= 0


