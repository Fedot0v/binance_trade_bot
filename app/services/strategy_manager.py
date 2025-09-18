from __future__ import annotations

from typing import Dict, Any


class BacktestStrategyManager:
    """Отвечает за выбор и создание стратегии в бэктесте (без внешних зависимостей)."""

    def determine_strategy_key(self, template, parameters: Dict[str, Any], default_name: str) -> str:
        # Явные признаки по шаблону/параметрам
        if parameters and ("compensation" in parameters or "compensation" in template.template_name.lower()):
            return "compensation"
        if parameters and ("novichok" in parameters or "novichok" in template.template_name.lower()):
            return "novichok"
        # Fallback: используем имя конфигурации стратегии
        return (default_name or "").lower()

    def make_strategy(self, strategy_key: str, template):
        from strategies.strategy_factory import make_strategy
        return make_strategy(strategy_key, template)

from typing import Dict, List, Optional
import pandas as pd

from services.deal_service import DealService
from services.strategy_log_service import StrategyLogService
from strategies.base_strategy import BaseStrategy
from schemas.strategy_log import StrategyLogCreate


class StrategyManager:
    """Управляет стратегиями и их состоянием"""
    
    def __init__(
        self,
        deal_service: DealService,
        log_service: StrategyLogService
    ):
        self.deal_service = deal_service
        self.log_service = log_service

    async def update_trailing_stops(
        self,
        deals: List,
        market_data: Dict[str, pd.DataFrame],
        session,
        client
    ):
        """Обновляет trailing stop для всех сделок"""
        for deal in deals:
            await self._update_deal_trailing_stop(deal, market_data, session, client)

    async def _update_deal_trailing_stop(
        self,
        deal,
        market_data: Dict[str, pd.DataFrame],
        session,
        client
    ):
        """Обновляет trailing stop для конкретной сделки"""
        symbol = self._get_symbol_string(deal.symbol)
        
        if symbol not in market_data:
            print(f"[TRAILING] Пропуск обновления: нет market_data для {symbol} | deal_id={getattr(deal, 'id', '?')}")
            return
            
        df = market_data[symbol]
        if df.empty:
            print(f"[TRAILING] Пропуск обновления: market_data пуст для {symbol} | deal_id={getattr(deal, 'id', '?')}")
            return
            
        current_price = float(df['close'].iloc[-1])
        
        # Получаем стратегию для сделки
        strategy = await self._get_strategy_for_deal(deal, session)
        if not strategy:
            print(f"[TRAILING] Стратегия не найдена для сделки {getattr(deal, 'id', '?')} — обновление SL не выполняется")
            return
            
        # Проверяем, нужно ли обновлять trailing stop
        print(f"[TRAILING] Проверка необходимости обновления SL | deal_id={getattr(deal, 'id', '?')} price={current_price}")
        if not strategy.should_update_trailing_stop(deal, current_price):
            print(f"[TRAILING] Обновление SL не требуется | deal_id={getattr(deal, 'id', '?')} price={current_price}")
            return
            
        # Рассчитываем новую цену trailing stop
        new_stop_price = strategy.calculate_trailing_stop_price(deal, current_price)
        if new_stop_price is None:
            print(f"[TRAILING] Не удалось рассчитать новую цену SL | deal_id={getattr(deal, 'id', '?')} price={current_price}")
            return
            
        print(f"[TRAILING] Обновление стоп-лосса для сделки {deal.id}: {new_stop_price:.4f}")
        
        # Обновляем в базе данных
        await self._update_deal_trailing_stop_in_db(deal, new_stop_price, current_price, session)
        
        # Обновляем ордер стоп-лосса на Binance
        try:
            await self.deal_service.update_stop_loss_order(deal, session, client, new_stop_price)
            print(f"[TRAILING] Стоп-лосс ордер обновлен на Binance: {new_stop_price:.4f}")
        except Exception as e:
            print(f"[TRAILING] Ошибка при обновлении стоп-лосс ордера: {e}")

    async def _update_deal_trailing_stop_in_db(
        self,
        deal,
        new_stop_price: float,
        current_price: float,
        session
    ):
        """Обновляет trailing stop в базе данных"""
        from repositories.deal_repository import DealRepository
        
        repo = DealRepository(session)
        
        # Обновляем стоп-лосс
        await repo.update_stop_loss(deal.id, new_stop_price, session)
        
        # Обновляем max_price/min_price для trailing stop
        if deal.side == 'BUY':
            await repo.update_max_price(deal.id, current_price, session)
        else:
            await repo.update_min_price(deal.id, current_price, session)

    async def check_strategy_exit_signals(
        self,
        deals: List,
        market_data: Dict[str, pd.DataFrame],
        session,
        client
    ):
        """Проверяет сигналы на выход из позиций по стратегиям"""
        for deal in deals:
            await self._check_deal_exit_signal(deal, market_data, session, client)

    async def _check_deal_exit_signal(
        self,
        deal,
        market_data: Dict[str, pd.DataFrame],
        session,
        client
    ):
        """Проверяет сигнал на выход для конкретной сделки"""
        # Получаем стратегию для сделки
        strategy = await self._get_strategy_for_deal(deal, session)
        if not strategy:
            return
            
        # Проверяем, нужно ли закрыть позицию
        if not strategy.should_close_position(deal, market_data):
            return
            
        print(f"[STRATEGY] Сигнал на закрытие позиции для сделки {deal.id}")
        
        # Закрываем позицию
        await self._close_deal_by_strategy(deal, session, client, strategy)

    async def _close_deal_by_strategy(
        self,
        deal,
        session,
        client,
        strategy
    ):
        """Закрывает сделку по сигналу стратегии"""
        symbol = self._get_symbol_string(deal.symbol)
        
        try:
            # Отменяем стоп-лосс ордер если он есть
            if deal.stop_loss_order_id:
                await self.deal_service.cancel_stop_loss_order(deal, session, client)
            
            # Получаем текущую цену
            price_info = await client.futures_mark_price(symbol=symbol)
            exit_price = float(price_info["markPrice"])
            
            # Рассчитываем PnL
            if deal.side == 'BUY':
                pnl = (exit_price - deal.entry_price) * deal.size
            else:
                pnl = (deal.entry_price - exit_price) * deal.size
            
            # Закрываем позицию на бирже
            close_side = 'SELL' if deal.side == 'BUY' else 'BUY'
            await client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='MARKET',
                quantity=deal.size,
                reduceOnly=True
            )
            
            # Закрываем сделку в базе
            await self.deal_service.close(
                deal.id,
                exit_price=exit_price,
                pnl=pnl,
                session=session,
                autocommit=False
            )
            
            # Добавляем лог
            await self.log_service.add_log(
                StrategyLogCreate(
                    user_id=deal.user_id,
                    deal_id=deal.id,
                    strategy=strategy.__class__.__name__,
                    signal="strategy_exit",
                    comment=f"Позиция закрыта по сигналу стратегии. Цена выхода: {exit_price}, PnL: {pnl:.2f}"
                ),
                session=session,
                autocommit=False
            )
            
            print(f"[STRATEGY] Сделка {deal.id} закрыта по сигналу стратегии")
            
        except Exception as e:
            print(f"[STRATEGY] Ошибка при закрытии сделки {deal.id}: {e}")

    async def _get_strategy_for_deal(self, deal, session) -> Optional[BaseStrategy]:
        """Получает стратегию для сделки"""
        try:
            # Во избежание async lazy-load (greenlet_spawn error) НЕ трогаем deal.template напрямую
            # Берём template_id и грузим шаблон явным запросом через AsyncSession
            template = None
            template_id = getattr(deal, 'template_id', None)
            if not template_id:
                print(f"[STRATEGY_RESOLVE] У сделки {getattr(deal, 'id', '?')} отсутствует template_id — стратегия не определена")
                return None
            try:
                from models.user_model import UserStrategyTemplate
                template = await session.get(UserStrategyTemplate, template_id)
            except Exception as e:
                print(f"[STRATEGY_RESOLVE] Ошибка загрузки шаблона по template_id={template_id}: {e}")
                return None
            if not template:
                print(f"[STRATEGY_RESOLVE] Шаблон с id={template_id} не найден — стратегия не определена")
                return None

            # Извлечём параметры шаблона
            params: Dict[str, Any] = {}
            if hasattr(template, 'parameters') and template.parameters:
                try:
                    if isinstance(template.parameters, dict):
                        params = dict(template.parameters)
                    else:
                        import json
                        params = json.loads(template.parameters)
                except Exception:
                    params = {}

            # Определим ключ стратегии
            strategy_key: Optional[str] = None
            template_name = str(getattr(template, 'template_name', '') or '').lower()
            params_text = str(params).lower()
            if 'compensation' in template_name or 'compensation' in params_text:
                strategy_key = 'compensation'
            elif 'novichok' in template_name or 'novichok' in params_text:
                strategy_key = 'novichok'
            else:
                # Пробуем достать имя из StrategyConfig
                try:
                    from repositories.strategy_config_repository import StrategyConfigRepository
                    repo = StrategyConfigRepository(session)
                    cfg = await repo.get_by_id(getattr(template, 'strategy_config_id', None)) if hasattr(template, 'strategy_config_id') else None
                    if cfg and getattr(cfg, 'name', None):
                        strategy_key = str(cfg.name).lower()
                except Exception as e:
                    print(f"[STRATEGY_RESOLVE] Ошибка чтения StrategyConfig: {e}")

            if not strategy_key:
                print(f"[STRATEGY_RESOLVE] Не удалось определить стратегию для deal_id={getattr(deal, 'id', '?')} по template={template_name}")
                return None

            # Создаём базовую стратегию (не адаптер), чтобы корректно работать с SL/Trailing
            from services.strategy_parameters import StrategyParameters
            underlying = None
            if strategy_key == 'novichok':
                from strategies.novichok_strategy import NovichokStrategy
                underlying = NovichokStrategy(StrategyParameters(raw=params))
            elif strategy_key == 'compensation':
                from strategies.compensation_strategy import CompensationStrategy
                # Для компенсации требуется интервал
                effective_params = dict(params)
                if hasattr(template, 'interval') and getattr(template, 'interval', None):
                    effective_params['interval'] = getattr(template, 'interval')
                underlying = CompensationStrategy(StrategyParameters(raw=effective_params))
            else:
                print(f"[STRATEGY_RESOLVE] Неизвестный ключ стратегии: {strategy_key}")
                return None

            # Вычислим trailing pct
            trailing_pct = float(getattr(underlying, 'trailing_stop_pct', params.get('trailing_stop_pct', 0.002)))

            # Обёртка, нормализующая сигнатуры методов
            manager = self
            class StrategyFacade(BaseStrategy):
                def __init__(self):
                    super().__init__({'trailing_stop_pct': trailing_pct})

                def generate_signal(self, df):
                    return 'hold'

                def calculate_position_size(self, balance: float) -> float:
                    return 0.0

                def should_close_position(self, deal, market_data):
                    # По умолчанию не используем закрытие по стратегии на лайве через менеджер
                    return False

                def should_update_trailing_stop(self, deal, current_price: float) -> bool:
                    try:
                        if hasattr(underlying, 'should_update_trailing_stop'):
                            return underlying.should_update_trailing_stop(deal, current_price)
                    except Exception:
                        pass
                    # Fallback логика
                    if not hasattr(deal, 'max_price') or not hasattr(deal, 'min_price'):
                        return False
                    if getattr(deal, 'side', 'BUY') == 'BUY':
                        return current_price > getattr(deal, 'max_price', deal.entry_price)
                    return current_price < getattr(deal, 'min_price', deal.entry_price)

                def calculate_trailing_stop_price(self, deal, current_price: float) -> Optional[float]:
                    # Попробуем определить сигнатуру метода у underlying
                    try:
                        meth = getattr(underlying, 'calculate_trailing_stop_price', None)
                        if callable(meth):
                            argcount = getattr(meth, '__code__', None).co_argcount if hasattr(meth, '__code__') else None
                            varnames = getattr(meth, '__code__', None).co_varnames if hasattr(meth, '__code__') else ()
                            # NovichokStrategy: (self, entry_price, current_price, side, symbol)
                            if argcount == 5 or (varnames and 'entry_price' in varnames and 'current_price' in varnames):
                                entry_price = float(getattr(deal, 'entry_price'))
                                side = 'long' if getattr(deal, 'side', 'BUY') == 'BUY' else 'short'
                                symbol = manager._get_symbol_string(getattr(deal, 'symbol', 'BTCUSDT'))
                                return meth(entry_price, float(current_price), side, symbol)
                            # BaseStrategy-style: (self, deal, current_price)
                            return meth(deal, float(current_price))
                    except Exception:
                        pass
                    # Fallback: рассчитаем по trailing_pct
                    if getattr(deal, 'side', 'BUY') == 'BUY':
                        return float(current_price) * (1 - trailing_pct)
                    return float(current_price) * (1 + trailing_pct)

            print(f"[STRATEGY_RESOLVE] Определена стратегия '{strategy_key}' для deal_id={getattr(deal, 'id', '?')} | trailing_pct={trailing_pct}")
            return StrategyFacade()
        except Exception as e:
            print(f"Ошибка при получении стратегии для сделки {deal.id}: {e}")
            return None

    def _get_symbol_string(self, symbol) -> str:
        """Преобразует символ в строку"""
        return symbol.value if hasattr(symbol, "value") else str(symbol)
