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
from services.trade_executor import TradeExecutor


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
            # 0) Проверяем активность бота (не останавливаемся из-за открытой сделки до выяснения стратегии)
            print(f"Проверка активности бота (user_id={user_id}, symbol={symbol}) и открытых сделок")
            bot = await self.userbot_service.get_active_bot(user_id, symbol)
            print(f"Текущий статус бота: {bot.status if bot else 'бот не найден'}")
            if not bot:
                print("Бот не активен")
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

            # 2.1) Определяем, есть ли открытая сделка по основному символу
            opened = await self.deal_service.get_open_deal_for_user_and_symbol(
                user_id,
                symbol
            )
            strategy_name_lower = str(getattr(strategy_config, 'name', '') or '').lower()
            if opened and strategy_name_lower != 'compensation':
                print("Открытая сделка уже существует — для стратегии не compensation новый вход не выполняется")
                return

            print("Шаг 3: Получение рыночных данных")
            md = {}
            if strategy_name_lower == 'compensation':
                # Для компенсационной стратегии получаем BTC и ETH
                btc_symbol = template.symbol.value
                eth_symbol = 'ETHUSDT'
                print(f"Компенсационная стратегия — запрашиваем данные для {btc_symbol} и {eth_symbol}")
                # BTC
                btc_klines = await self.marketdata_service.get_klines(
                    api_key, api_secret,
                    symbol=btc_symbol,
                    interval=template.interval.value,
                    limit=500
                )
                btc_df = pd.DataFrame(btc_klines, columns=[
                    'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                    'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                # Приводим числовые столбцы к float
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    btc_df[col] = btc_df[col].astype(float)
                # Индекс по времени для корректных временных фильтраций/синхронизаций
                btc_df['open_time'] = pd.to_datetime(btc_df['open_time'], unit='ms')
                btc_df = btc_df.set_index('open_time')
                md[btc_symbol] = btc_df
                print(f"Свечи {btc_symbol}: {btc_df.tail(3).to_dict('records')}")
                # ETH
                eth_klines = await self.marketdata_service.get_klines(
                    api_key, api_secret,
                    symbol=eth_symbol,
                    interval=template.interval.value,
                    limit=500
                )
                eth_df = pd.DataFrame(eth_klines, columns=[
                    'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                    'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                # Приводим числовые столбцы к float
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    eth_df[col] = eth_df[col].astype(float)
                # Индекс по времени для корректных временных фильтраций/синхронизаций
                eth_df['open_time'] = pd.to_datetime(eth_df['open_time'], unit='ms')
                eth_df = eth_df.set_index('open_time')
                md[eth_symbol] = eth_df
                print(f"Свечи {eth_symbol}: {eth_df.tail(3).to_dict('records')}")
            else:
                df = await self._get_market_data(api_key, api_secret, template)
                print(f"Свечи: {df.tail(3).to_dict('records')}")
                md = {self._sym_str(template.symbol): df}

            print("Шаг 4: Решение стратегии")
            strategy = make_strategy(strategy_config.name, template)
            # Готовим open_state из БД: это нужно для компенсации
            open_state = {}
            try:
                # Основной символ (BTCUSDT)
                main_symbol = self._sym_str(template.symbol)
                main_open = await self.deal_service.get_open_deal_for_user_and_symbol(user_id, main_symbol)
                if main_open:
                    open_state[main_symbol] = {
                        'position': {
                            'entry_price': float(getattr(main_open, 'entry_price', 0.0)),
                            'entry_time': getattr(main_open, 'opened_at', None),
                            'side': getattr(main_open, 'side', 'BUY'),
                            'size': float(getattr(main_open, 'size', 0.0)),
                            'stop_loss': getattr(main_open, 'stop_loss', None),
                            'max_price': getattr(main_open, 'max_price', None),
                            'min_price': getattr(main_open, 'min_price', None),
                        }
                    }
                # ETH позиция, если компенсация
                if strategy_name_lower == 'compensation':
                    eth_symbol = 'ETHUSDT'
                    eth_open = await self.deal_service.get_open_deal_for_user_and_symbol(user_id, eth_symbol)
                    if eth_open:
                        open_state[eth_symbol] = {
                            'position': {
                                'entry_price': float(getattr(eth_open, 'entry_price', 0.0)),
                                'entry_time': getattr(eth_open, 'opened_at', None),
                                'side': getattr(eth_open, 'side', 'BUY'),
                                'size': float(getattr(eth_open, 'size', 0.0)),
                                'stop_loss': getattr(eth_open, 'stop_loss', None),
                                'max_price': getattr(eth_open, 'max_price', None),
                                'min_price': getattr(eth_open, 'min_price', None),
                            }
                        }

                    # ДОПОЛНИТЕЛЬНО: если BTC уже закрыт (нет open), попробуем гидратировать состояние компенсации
                    if not main_open:
                        last_closed_btc = await self.deal_service.get_last_closed_deal_for_user_and_symbol(user_id, main_symbol)
                        if last_closed_btc and hasattr(strategy, 'strategy') and hasattr(strategy.strategy, 'update_state'):
                            # Передадим в состояние цену входа и сторону BTC, а также отметим время закрытия
                            try:
                                strategy.strategy.update_state(
                                    btc_entry_price=float(getattr(last_closed_btc, 'entry_price', 0.0)),
                                    btc_entry_time=getattr(last_closed_btc, 'opened_at', None),
                                    btc_side=getattr(last_closed_btc, 'side', None)
                                )
                                # Пометим время закрытия, чтобы can_compensate_after_close работал
                                if hasattr(strategy.strategy, 'mark_btc_closed') and hasattr(last_closed_btc, 'closed_at') and getattr(last_closed_btc, 'closed_at', None):
                                    strategy.strategy.state.btc_closed_time = getattr(last_closed_btc, 'closed_at')
                                    print(f"[COMP] Гидратация пост-компенсации: BTC закрыт в {strategy.strategy.state.btc_closed_time}, entry={strategy.strategy.state.btc_entry_price}, side={strategy.strategy.state.btc_side}")
                            except Exception as e:
                                print(f"[COMP] Ошибка гидратации состояния для пост-компенсации: {e}")
            except Exception as e:
                print(f"Ошибка построения open_state: {e}")

            decision = await strategy.decide(md, template, open_state=open_state)

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
        try:
            t_name = getattr(template, 'template_name', None) or getattr(template, 'name', None) or str(template)
            print(f"Актуальный шаблон стратегии: {t_name}")
        except Exception:
            print(f"Актуальный шаблон стратегии: {str(template)}")
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
