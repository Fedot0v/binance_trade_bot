from app.clients.client_factory import ExchangeClientFactory


class TradeService:
    def __init__(
        self,
        strategy_service,
        deal_service,
        marketdata_service,
        apikeys_service,
        user_settings_service,
        log_service,
        exchange_client_factory: ExchangeClientFactory,
    ):
        self.strategy_service = strategy_service
        self.deal_service = deal_service
        self.marketdata_service = marketdata_service
        self.apikeys_service = apikeys_service
        self.user_settings_service = user_settings_service
        self.log_service = log_service
        self.exchange_client_factory = exchange_client_factory

    async def run_trading_cycle(self, user_id: int):
        # 1. Получить настройки и ключи пользователя
        apikey = await self.apikeys_service.get_by_user(user_id)
        settings = await self.user_settings_service.get_by_user_id(user_id)
        strategy_config = await self.strategy_service.get_active_for_user(user_id)
        
        # 2. Создать binance_client через фабрику
        # Создаём клиента нужной биржи через фабрику (всегда await!)
        exchange_client = await self.exchange_client_factory.create(api_key=apikey.api_key, api_secret=apikey.api_secret)


        # 3. Получить свежие данные рынка
        market_data = await self.marketdata_service.get_latest(symbol=settings.symbol)
        
        # 4. Прогнать данные через стратегию и получить сигнал
        signal = await self.strategy_service.generate_signal(strategy_config, market_data)
        
        # 5. Если есть сигнал — открыть/закрыть сделку через DealService и через binance_client
        if signal in ("long", "short"):
            # Пример: создать ордер на Binance
            order_result = await exchange_client.create_order(...)
            # Пример: создать сделку у себя
            await self.deal_service.create_from_signal(user_id, signal, order_result, ...)
            await self.log_service.add_log(user_id, f"Открыта сделка {signal}")
        # ...и аналогично для стоп-лоссов/тейк-профитов/переворотов

        # 6. Логирование и уведомления
        await self.log_service.add_log(user_id, f"Торговый цикл завершён")

    async def start_trading(self, user_id: int):
        # Здесь должен быть запуск фоновой задачи, например через background tasks, Celery или internal loop
        # Для MVP можно просто вызвать run_trading_cycle
        await self.run_trading_cycle(user_id)
        # Для реального бота — зафиксировать статус “запущен”, например в памяти или Redis

    async def stop_trading(self, user_id: int):
        # Здесь остановка фоновой задачи (если она есть)
        # Или просто запись статуса "остановлен"
        pass

    async def get_bot_status(self, user_id: int) -> str:
        # Тут нужно возвращать актуальный статус бота (запущен/остановлен)
        # Например, хранить в dict {user_id: status} (MVP) или в Redis
        return "stopped"  # или "running", "error", "not_started" и т.д.

    async def get_logs(self, deal_id: int):
        # Получение логов для вывода в UI/REST
        # Например, через log_service.get_by_user(user_id)
        return await self.log_service.get_by_deal(deal_id)
