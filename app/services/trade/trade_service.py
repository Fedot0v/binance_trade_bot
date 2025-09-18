from uuid import UUID
import asyncio

import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

from clients.client_factory import ExchangeClientFactory
from strategies.base_strategy import BaseStrategy
from services.apikeys_service import APIKeysService
from services.deal_service import DealService
from services.marketdata_service import MarketDataService
from services.user_strategy_template_service import UserStrategyTemplateService
from services.strategy.strategy_log_service import StrategyLogService
from schemas.user_strategy_template import UserStrategyTemplateRead
from services.strategy.strategy_config_service import StrategyConfigService
from strategies.strategy_factory import make_strategy, get_strategy_class_by_name
from strategies.contracts import Decision, OrderIntent
from services.balance_service import BalanceService
from services.order_service import OrderService
from encryption.crypto import decrypt
from schemas.deal import DealCreate
from services.bot_service import UserBotService
from schemas.strategy_log import StrategyLogCreate
from services.strategy.strategy_parameters import StrategyParameters
from services.trade.trade_executor import TradeExecutor


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
        
        # Создаем TradeExecutor
        self.trade_executor = TradeExecutor(
            exchange_client_factory=exchange_client_factory,
            balance_service=balance_service,
            order_service=order_service,
            deal_service=deal_service,
            log_service=log_service,
            apikeys_service=apikeys_service,
            marketdata_service=self.marketdata_service # Добавляем marketdata_service
        )

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
            params = StrategyParameters(raw=template.parameters)
            print(f"Параметры стратегии: {params.as_dict()}")
            strategy_config = await self.strategy_config_service.get_by_id(
                template.strategy_config_id
            )
            print(f"Стратегия из конфигов: {strategy_config}")

            print("Шаг 3: Получение рыночных данных")
            # Определяем, какие символы нужны
            required_symbols = [self._sym_str(template.symbol)]
            if strategy_config.name.lower() == "compensation":
                required_symbols.append("ETHUSDT") # Предполагаем, что второй символ всегда ETHUSDT
                print(f"Компенсационная стратегия, запрашиваем данные для: {required_symbols}")

            market_data = await self._get_market_data(api_key, api_secret, template, required_symbols)
            for sym, df in market_data.items():
                print(f"Свечи для {sym}: {df.tail(3).to_dict('records')}")


            print("Шаг 4: Решение стратегии")
            strategy = make_strategy(strategy_config.name, template)
            # symbol_str = self._sym_str(template.symbol) # Больше не нужен, т.к. market_data уже содержит все символы

            # Синхронизируем данные, если их несколько
            if len(market_data) > 1:
                from services.backtest.market_data_utils import MarketDataUtils
                btc_df = market_data.get("BTCUSDT")
                eth_df = market_data.get("ETHUSDT")
                if btc_df is not None and eth_df is not None:
                    btc_df, eth_df = MarketDataUtils.synchronize_pair(btc_df, eth_df)
                    market_data["BTCUSDT"] = btc_df
                    market_data["ETHUSDT"] = eth_df
                else:
                    print("WARNING: Не удалось синхронизировать BTC/ETH данные, один из них отсутствует.")

            # Формируем open_state на основе открытых сделок
            open_state = {}
            for sym in required_symbols:
                open_deal = await self.deal_service.get_open_deal_for_user_and_symbol(user_id, sym)
                if open_deal:
                    open_state[sym] = {
                        "deal_id": open_deal.id,
                        "entry_price": open_deal.entry_price,
                        "entry_time": open_deal.entry_time,
                        "side": open_deal.side,
                        "position": open_deal # Передаем полный объект сделки
                    }
            print(f"Актуальный open_state: {open_state}")

            decision = await strategy.decide(market_data, template, open_state=open_state)

            print(f"Decision: intents={len(decision.intents)}, ttl={decision.bundle_ttl_sec}")
            if not decision.intents:
                print("Решение пустое — пропуск")
                return

            print("Шаг 5: Исполнение намерений через TradeExecutor")
            for intent in decision.intents:
                await self.trade_executor.execute_intent(
                    intent=intent,
                    template=template,
                    user_id=user_id,
                    bot_id=bot_id,
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

    async def _get_market_data(self, api_key: str, api_secret: str, template: UserStrategyTemplateRead, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        all_dfs = {}
        print(f"Получаем рыночные данные для символов: {symbols}, interval={template.interval.value}")
        for symbol_str in symbols:
            klines = await self.marketdata_service.get_klines(
                api_key, api_secret,
                symbol=symbol_str,
                interval=template.interval.value,
                limit=500
            )
            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            df['close'] = df['close'].astype(float)
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df = df.set_index('open_time')
            all_dfs[symbol_str] = df
        return all_dfs

    def _sym_str(self, x) -> str:
        return x.value if hasattr(x, "value") else str(x)

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
