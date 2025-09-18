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
from services.strategy.strategy_log_service import StrategyLogService
from strategies.base_strategy import BaseStrategy
from schemas.strategy_log import StrategyLogCreate
from services.strategy.strategy_config_service import StrategyConfigService


class StrategyManager:
    """Управляет стратегиями и их состоянием"""
    
    def __init__(
        self,
        deal_service: DealService,
        log_service: StrategyLogService,
        strategy_config_service: StrategyConfigService
    ):
        self.deal_service = deal_service
        self.log_service = log_service
        self.strategy_config_service = strategy_config_service

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
            return
            
        df = market_data[symbol]
        if df.empty:
            return
            
        current_price = float(df['close'].iloc[-1])
        
        # Получаем стратегию для сделки
        strategy = await self._get_strategy_for_deal(deal)
        if not strategy:
            return
            
        # Проверяем, нужно ли обновлять trailing stop
        if not strategy.should_update_trailing_stop(deal, current_price):
            return
            
        # Рассчитываем новую цену trailing stop
        new_stop_price = strategy.calculate_trailing_stop_price(deal, current_price)
        if new_stop_price is None:
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
        
        repo = DealRepository()
        
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
        strategy = await self._get_strategy_for_deal(deal)
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

    async def _get_strategy_for_deal(self, deal) -> Optional[BaseStrategy]:
        """Получает стратегию для сделки"""
        try:
            if not deal.strategy_config_id:
                print(f"Сделка {deal.id} не имеет strategy_config_id.")
                return None

            strategy_config = await self.strategy_config_service.get_by_id(deal.strategy_config_id)
            if not strategy_config:
                print(f"Не найдена конфигурация стратегии с ID {deal.strategy_config_id} для сделки {deal.id}.")
                return None

            # Создаем временный объект шаблона для make_strategy
            class TempTemplate:
                def __init__(self, parameters: Dict[str, Any]):
                    self.parameters = parameters

            # Предполагаем, что параметры стратегии хранятся в strategy_config
            template = TempTemplate(parameters=strategy_config.parameters)

            from strategies.strategy_factory import make_strategy
            strategy = make_strategy(strategy_config.name, template)
            return strategy
        except Exception as e:
            print(f"Ошибка при получении стратегии для сделки {deal.id}: {e}")
            return None

    def _get_symbol_string(self, symbol) -> str:
        """Преобразует символ в строку"""
        return symbol.value if hasattr(symbol, "value") else str(symbol)
