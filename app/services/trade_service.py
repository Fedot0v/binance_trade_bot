from uuid import UUID
import asyncio

import pandas as pd

from clients.client_factory import ExchangeClientFactory
from strategies.base_strategy import BaseStrategy
from services.apikeys_service import APIKeysService
from services.deal_service import DealService
from services.marketdata_service import MarketDataService
from services.user_strategy_template_service import UserStrategyTemplateService
from services.strategy_log_service import StrategyLogService
from schemas.user_strategy_template import UserStrategyTemplateRead
from services.strategy_config_service import StrategyConfigService
from strategies.strategy_factory import make_strategy, get_strategy_class_by_name
from strategies.contracts import Decision, OrderIntent
from services.balance_service import BalanceService
from services.order_service import OrderService
from encryption.crypto import decrypt
from schemas.deal import DealCreate
from services.bot_service import UserBotService
from schemas.strategy_log import StrategyLogCreate
from services.strategy_parameters import StrategyParameters


TRAIL_PCT = 0.002


def _sym_str(x) -> str:
    return x.value if hasattr(x, "value") else str(x)


class TradeService:
    def __init__(
        self,
        deal_service: DealService,
        marketdata_service: MarketDataService,
        apikeys_service: APIKeysService,
        user_strategy_template_service: UserStrategyTemplateService,
        log_service: StrategyLogService,
        exchange_client_factory: ExchangeClientFactory,
        strategy_config_service: StrategyConfigService,
        balance_service: BalanceService,
        order_service: OrderService,
        userbot_service: UserBotService
    ):
        self.deal_service = deal_service
        self.marketdata_service = marketdata_service
        self.apikeys_service = apikeys_service
        self.user_strategy_template_service = user_strategy_template_service
        self.log_service = log_service
        self.exchange_client_factory = exchange_client_factory
        self.balance_service = balance_service
        self.order_service = order_service
        self.strategy_config_service = strategy_config_service
        self.userbot_service = userbot_service

    async def run_trading_cycle(
        self,
        bot_id,
        user_id,
        symbol,
        session=None
    ):
        print(f"=== START: Trading Cycle | bot_id={bot_id} user_id={user_id} symbol={symbol} ===")
        async with session.begin():
            if not await self._check_bot_and_deal(bot_id, user_id, symbol):
                print("Остановлено: нет активного бота или уже есть открытая сделка")
                return

            print("Шаг 1: Получение API-ключей и шаблона стратегии")
            api_key, api_secret, template = await self._get_keys_and_template(
                user_id
            )
            print(
                f"Получены ключи: api_key (скрыт), \
                    api_secret (скрыт), template: {template}"
            )
            if not api_key:
                print("API ключ не найден, остановка")
                return

            print("Шаг 2: Инициализация параметров стратегии")
            params = StrategyParameters(template.parameters)
            print(f"Параметры стратегии: {params.as_dict()}")
            strategy_config = await self.strategy_config_service.get_by_id(
                template.strategy_config_id
            )
            print(f"Стратегия из конфигов: {strategy_config}")

            print("Шаг 3: Получение рыночных данных")
            df = await self._get_market_data(api_key, api_secret, template)
            print(f"Свечи: {df.tail(3).to_dict('records')}")

            print("Шаг 4: Решение стратегии")
            strategy = make_strategy(strategy_config.name, template)
            symbol_str = _sym_str(template.symbol)
            md = {symbol_str: df}
            decision = await strategy.decide(md, template, open_state={})

            print(f"Decision: intents={len(decision.intents)}, ttl={decision.bundle_ttl_sec}")
            if not decision.intents:
                print("Решение пустое — пропуск")
                return

            print("Шаг 5: Исполнение намерений")
            for intent in decision.intents:
                await self._execute_intent_from_decision(
                    user_id=user_id,
                    bot_id=bot_id,
                    template=template,
                    intent=intent,
                    md=md,
                    api_key=api_key,
                    api_secret=api_secret,
                    session=session,
                    strategy=strategy
                )

        print("=== END: Trading Cycle ===")

    async def _check_bot_and_deal(self, bot_id, user_id, symbol):
        print(f"Проверка активности бота (user_id={user_id}, symbol={symbol}) и открытых сделок")
        bot = await self.userbot_service.get_active_bot(user_id, symbol)
        print(f"Текущий статус бота: {bot.status if bot else 'бот не найден'}")
        if not bot:
            print("Бот не активен")
            return False
        opened = await self.deal_service.get_open_deal_for_user_and_symbol(
            user_id,
            symbol
        )
        print(f"Есть открытая сделка по паре? {'Да' if opened else 'Нет'}")
        if opened:
            print("Открытая сделка уже существует")
            return False
        return True

    async def _get_keys_and_template(self, user_id):
        apikeys = await self.apikeys_service.get_active(user_id)
        print(f"Активных API-ключей: {len(apikeys)}")
        if not apikeys:
            await self.log_service.add_log_user(user_id, "Нет API ключей")
            return None, None, None

        api_key = apikeys[0].api_key_encrypted
        api_secret = decrypt(apikeys[0].api_secret_encrypted)
        template = (
            await self.user_strategy_template_service.get_active_strategie(
                user_id
            )
        )
        print(f"Актуальный шаблон стратегии: {template}")
        if not template:
            await self.log_service.add_log_user(
                user_id,
                "Нет активного шаблона стратегии"
            )
            return None, None, None

        return api_key, api_secret, template

    async def _get_market_data(self, api_key, api_secret, template):
        print(f"Получаем рыночные данные: symbol={template.symbol.value}, interval={template.interval.value}")
        klines = await self.marketdata_service.get_klines(
            api_key, api_secret,
            symbol=template.symbol.value,
            interval=template.interval.value,
            limit=500
        )
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
        return df

    def _generate_signal(self, strategy_config, df):
        print(f"Генерация сигнала по стратегии: {strategy_config.name}")
        params = StrategyParameters(strategy_config.parameters)
        strat = get_strategy_class_by_name(strategy_config.name, params)
        signal = strat.generate_signal(df)
        print(f"Сгенерированный сигнал: {signal}")
        return signal

    async def _calculate_position(self, api_key, api_secret, template, df):
        balance_data = await self.balance_service.get_futures_balance(
            api_key,
            api_secret,
            asset="USDT"
        )
        balance = balance_data["available"]
        print(f"Доступный баланс по API: {balance}")
        params = StrategyParameters(template.parameters)

        strategy_config = await self.strategy_config_service.get_by_id(
            template.strategy_config_id
        )
        strategy = get_strategy_class_by_name(strategy_config.name, params)

        size = strategy.calculate_position_size(balance)
        price = df['close'].iloc[-1]
        quantity = round(size / price, 3)
        print(f"Рассчитано: quantity={quantity} (size={size}/price={price})")
        return quantity, price

    async def _place_order(self, api_key, api_secret, template, signal, quantity, symbol_override: str | None = None):
        order_side = "BUY" if signal == "long" else "SELL"
        symbol_val = symbol_override or template.symbol.value
        print(f"Создание ордера: symbol={symbol_val}, side={order_side}, quantity={quantity}, leverage={template.leverage}")
        result = await self.order_service.create_order(
            api_key, api_secret,
            symbol=symbol_val,
            side=order_side,
            quantity=quantity,
            leverage=int(template.leverage),
            order_type="MARKET"
        )
        print(f"Создан ордер: {result}")
        return result

    async def _fetch_entry_price(self, api_key, api_secret, symbol, order_id):
        print(f"Получение entry_price по ордеру: symbol={symbol}, orderId={order_id}")
        client = await self.exchange_client_factory.create(
            api_key,
            api_secret,
            exchange="binance"
        )
        max_retries = 5
        entry_price = 0.0
        for i in range(max_retries):
            order_info = await client.futures_get_order(
                symbol=symbol,
                orderId=order_id
            )
            print(f"Инфо по ордеру ({i+1}): {order_info}")
            avg_price = float(order_info.get("avgPrice") or 0.0)
            executed_qty = float(order_info.get("executedQty") or 0.0)
            cum_quote = float(order_info.get("cumQuote") or 0.0)
            entry_price = avg_price if avg_price > 0 else (
                cum_quote / executed_qty if executed_qty > 0 else 0.0
            )
            if entry_price > 0:
                print(f"Entry price получен: {entry_price}")
                break
            print(f"Ожидание исполнения ордера... Попытка {i+1}")
            await asyncio.sleep(1)
        if entry_price == 0.0:
            raise Exception("Не удалось получить entry_price после 5 попыток")
        return entry_price

    async def _record_deal(
        self,
        user_id,
        bot_id,
        template,
        entry_price,
        order_result,
        signal,
        strategy_config,
        size,
        session,
        symbol_override: str | None = None,
        strategy=None
    ):
        print("Сохранение сделки в базе данных")
        side = "BUY" if signal == "long" else "SELL"
        symbol_val = symbol_override or getattr(template.symbol, "value", str(template.symbol))

        # Используем стратегию для расчета стоп-лосса, если она передана
        if strategy and hasattr(strategy, 'calculate_stop_loss_price'):
            stop_loss_price = strategy.calculate_stop_loss_price(entry_price, side)
            print(f"Стоп-лосс рассчитан стратегией: {stop_loss_price:.4f}")
        else:
            # Fallback на старую логику
            TRAIL_PCT = 0.002
            stop_loss_price = entry_price * (1 - TRAIL_PCT) if side == "BUY" else entry_price * (1 + TRAIL_PCT)
            print(f"Стоп-лосс рассчитан по умолчанию: {stop_loss_price:.4f}")

        deal_data = DealCreate(
            user_id=user_id,
            bot_id=bot_id,
            template_id=template.id,
            order_id=str(order_result["orderId"]),
            symbol=symbol_val,
            side="BUY" if signal == "long" else "SELL",
            entry_price=entry_price,
            size=size,
            status="open",
            stop_loss=float(stop_loss_price)
        )
        print(f"Данные для записи сделки: {deal_data}")
        deal = await self.deal_service.create(
            deal_data,
            session,
            autocommit=False
        )
        print(f"Сделка записана в базе, id={deal.id}")
        
        # Создаем стоп лосс ордер на Binance
        try:
            # Получаем API ключи для создания клиента
            keys = await self.apikeys_service.get_decrypted_by_user(user_id)
            keys = keys[0] if keys else None
            if keys:
                client = await self.exchange_client_factory.create(
                    keys.api_key_encrypted, keys.api_secret_encrypted, exchange="binance"
                )
                try:
                    # Создаем стоп лосс ордер
                    stop_loss_order_id = await self.deal_service.create_stop_loss_order(
                        deal, session, client, stop_loss_price
                    )
                    print(f"Стоп-лосс ордер создан на Binance: {stop_loss_order_id}")
                finally:
                    await self.exchange_client_factory.close(client)
            else:
                print("Не удалось получить API ключи для создания стоп-лосс ордера")
        except Exception as e:
            print(f"Ошибка при создании стоп-лосс ордера: {e}")
            # Продолжаем работу даже если стоп-лосс ордер не создался
        
        await self.log_service.add_log(
            StrategyLogCreate(
                user_id=user_id,
                deal_id=deal.id,
                strategy=strategy_config.name,
                signal=signal,
                comment=f"Сделка открыта через Binance, ордер: {order_result.get('orderId')}"
            ),
            session=session,
            autocommit=False
        )
        print(f"Лог по сделке {deal.id} добавлен")

    async def start_trading(self, user_id, session=None):
        print("=== Вызов start_trading ===")
        await self.run_trading_cycle(
            user_id,
            session=session,
            )

    async def stop_trading(self, user_id: UUID, session):
        bot = await self.userbot_service.get_active_bot(user_id, "BTCUSDT")
        print(bot.status)
        await self.userbot_service.stop_bot(bot.id, session)

    async def get_bot_status(self, user_id: UUID) -> str:
        return "stopped"

    async def get_logs(self, deal_id: int):
        return await self.log_service.get_logs_by_deal(deal_id)

    async def _execute_intent_from_decision(self, user_id, bot_id, template, intent, md, api_key, api_secret, session, strategy=None):
        symbol_str = intent.symbol
        df_symbol = md.get(symbol_str)
        if df_symbol is None or df_symbol.empty:
            # подгрузка на случай, если стратегия вернула другой символ (на будущее)
            kl = await self.marketdata_service.get_klines(
                api_key, api_secret,
                symbol=symbol_str,
                interval=template.interval.value,
                limit=500
            )
            df_symbol = pd.DataFrame(kl, columns=[
                'open_time','open','high','low','close','volume','close_time',
                'quote_asset_volume','number_of_trades','taker_buy_base','taker_buy_quote','ignore'
            ])
            df_symbol['close'] = df_symbol['close'].astype(float)

        last_price = float(df_symbol['close'].iloc[-1])

        # sizing -> usd_size
        sizing = getattr(intent, "sizing", "usd")
        if sizing == "risk_pct":
            bal = await self.balance_service.get_futures_balance(api_key, api_secret, asset="USDT")
            usd_size = float(bal["available"]) * float(intent.size)   # intent.size в долях (0..1]
        elif sizing == "usd":
            usd_size = float(intent.size)
        elif sizing == "qty":
            # реже используется; оставим поддержку
            qty_direct = float(intent.size)
            usd_size = qty_direct * last_price
        else:
            print(f"Неизвестный sizing: {sizing}, пропуск")
            return

        # qty (оставляю твою текущую логику; квантование stepSize подключим позже)
        quantity = round(usd_size / last_price, 3)
        order_side = intent.side  # BUY/SELL
        legacy_signal = 'long' if order_side == 'BUY' else 'short'  # чтобы переиспользовать существующие методы

        print("Создание ордера (по intent)")
        order_result = await self._place_order(
            api_key, api_secret,
            template=template,
            signal=legacy_signal,
            quantity=quantity,
            symbol_override=symbol_str  # <— см. изменение сигнатуры ниже
        )

        print("Получение entry price")
        entry_price = await self._fetch_entry_price(api_key, api_secret, symbol_str, order_result['orderId'])

        print("Запись сделки и логов")
        strategy_config = await self.strategy_config_service.get_by_id(template.strategy_config_id)
        await self._record_deal(
            user_id=user_id,
            bot_id=bot_id,
            template=template,
            entry_price=entry_price,
            order_result=order_result,
            signal=legacy_signal,
            strategy_config=strategy_config,
            size=quantity,
            session=session,
            symbol_override=symbol_str,
            strategy=strategy
        )
