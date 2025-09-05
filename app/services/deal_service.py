from uuid import UUID
from typing import Optional

from fastapi import HTTPException, Depends

from repositories.deal_repository import DealRepository
from schemas.deal import DealCreate, DealRead, DealDelete
from encryption.crypto import decrypt
from schemas.strategy_log import StrategyLogCreate
from services.strategy_config_service import StrategyConfigService


class DealService:
    def __init__(
        self,
        repo: DealRepository,
        binance_client=None,
        apikeys_service=None,
        log_service=None,
        strategy_config_service: StrategyConfigService = None,
        strategy_manager=None
    ):
        self.repo = repo
        self.binance_client = binance_client
        self.apikeys_service = apikeys_service
        self.log_service = log_service
        self.strategy_config_service = strategy_config_service
        self.strategy_manager = strategy_manager

    async def create(
        self,
        data: DealCreate,
        session,
        autocommit: bool = True
    ) -> DealRead:
        print(f"Создание сделки: {data}")
        result = await self.repo.add(**data.model_dump())
        print(f"Сделка создана (ID {getattr(result, 'id', '?')})")
        if autocommit:
            await session.commit()
            print("Транзакция сохранена (commit)")
        return DealRead.model_validate(result)

    async def _get_strategy_name(self, deal) -> str:
        try:
            if not self.strategy_config_service:
                return "Unknown"
            
            if hasattr(deal, 'template') and deal.template:
                template = deal.template
                if hasattr(template, 'strategy_config_id'):
                    strategy_config = await self.strategy_config_service.get_by_id(
                        template.strategy_config_id
                    )
                    if strategy_config and hasattr(strategy_config, 'name'):
                        return strategy_config.name
            
            return "Unknown"
        except Exception as e:
            print(f"Ошибка при получении названия стратегии: {e}")
            return "Unknown"

    async def get_all(self) -> list[DealRead]:
        print("Получение всех сделок")
        deals = await self.repo.get_all()
        print(f"Найдено сделок: {len(deals)}")
        return [DealRead.model_validate(deal) for deal in deals]

    async def delete_by_id(
        self,
        deal_id: int,
        session,
        autocommit: bool = True
    ):
        print(f"Удаление сделки с ID {deal_id}")
        await self.repo.delete_deal(deal_id, session)
        if autocommit:
            await session.commit()
            print("Транзакция сохранена (commit после удаления)")
        return DealDelete(id=deal_id, message="Сделка успешно удалена")

    async def get_by_id(self, deal_id: int, session):
        print(f"Получение сделки по ID {deal_id}")
        deal = await self.repo.get_by_id(deal_id, session)
        if deal:
            print(f"Сделка найдена: {deal}")
            return DealRead.model_validate(deal)
        print(f"Сделка с ID {deal_id} не найдена")
        raise HTTPException(
            status_code=404,
            detail=f"Сделка с ID {deal_id} не найдена"
        )

    async def get_open_deal_for_user_and_symbol(self, user_id, symbol):
        print(f"Поиск открытой сделки для user_id={user_id}, symbol={symbol}")
        deal = await self.repo.get_open_deal_by_symbol(user_id, symbol)
        print(
            f"Найдена открытая сделка: {deal}"
            if deal
            else "Открытых сделок нет"
        )
        return deal

    async def close(
        self,
        deal_id: int,
        exit_price: float,
        pnl: float,
        session,
        autocommit: bool = True
    ):
        print(
            f"Закрытие сделки: ID={deal_id},\
                exit_price={exit_price}, pnl={pnl}"
        )
        await self.repo.close_deal(
            deal_id,
            exit_price=exit_price,
            pnl=pnl,
            session=session
        )
        if autocommit:
            await session.commit()
            print("Транзакция сохранена (commit после закрытия)")

    async def get_all_open_deals(self, session):
        print("Получение всех открытых сделок (статус 'open')")
        deals = await self.repo.get_open_deals(session)
        print(f"Всего открытых сделок: {len(deals)}")
        return deals

    async def watcher_cycle(self, session):
        print("== Запуск цикла слежения за сделками ==")
        open_deals = await self.get_all_open_deals(session)
        print(f"Всего сделок для проверки: {len(open_deals)}")
        for deal in open_deals:
            await self._process_open_deal(deal, session)

    async def _process_open_deal(self, deal, session):
        print(f"Проверка сделки: {deal}")
        keys = await self.apikeys_service.get_decrypted_by_user(deal.user_id)
        keys = keys[0] if keys else None
        if not keys:
            print(
                f"Нет API ключей для user_id={deal.user_id}, сделка пропущена"
            )
            return

        print(f"API-ключ (частично скрыт): {keys.api_key_encrypted[:6]}***")
        client_testnet_status = self.binance_client.testnet
        print(
            f"API-ключ найден для user_id={deal.user_id},\
                создаём бинанс-клиент. Используем testnet={client_testnet_status}"
        )
        client = await self.binance_client.create(
            keys.api_key_encrypted, keys.api_secret_encrypted, testnet=client_testnet_status
        )
        try:
            await self._sync_deal_with_binance(deal, session, client)
        finally:
            await self.binance_client.close(client)
            print(f"Бинанс-клиент закрыт для user_id={deal.user_id}")

    async def _sync_deal_with_binance(self, deal, session, client):
        symbol = (
            deal.symbol.value
            if hasattr(deal.symbol, "value")
            else deal.symbol
        )
        print(
            f"Синхронизация статуса сделки c Binance: symbol={symbol},\
                order_id={deal.order_id}, stop_loss_order_id={deal.stop_loss_order_id}"
        )
        
        # Сначала проверяем статус стоп лосс ордера
        if deal.stop_loss_order_id:
            stop_loss_executed = await self.check_stop_loss_order_status(deal, session, client)
            if stop_loss_executed:
                print(f"Сделка {deal.id} закрыта по стоп лоссу на Binance")
                return  # Сделка уже закрыта, дальше не проверяем
        
        # Проверяем основной ордер
        order_info = await client.futures_get_order(
            symbol=symbol,
            orderId=int(deal.order_id)
        )
        print(f"Информация о статусе ордера: {order_info}")
        binance_status = order_info['status']

        if binance_status in ('CANCELED', 'EXPIRED', 'REJECTED'):
            print(
                f"Статус ордера: {binance_status}.\
                    Закрываем сделку {deal.id} в базе"
            )
            # Отменяем стоп лосс ордер если он есть
            if deal.stop_loss_order_id:
                await self.cancel_stop_loss_order(deal, session, client)
            
            await self.repo.close_deal(deal.id, session)
            await session.commit()
            print(
                f"Сделка {deal.id} помечена как закрытая (по статусу Binance)"
            )
            return

        # Если есть StrategyManager, используем его для trailing stop
        if self.strategy_manager:
            try:
                # Получаем рыночные данные для trailing stop
                from services.marketdata_service import MarketDataService
                marketdata_service = MarketDataService()
                
                # Получаем данные для символа сделки
                klines = await marketdata_service.get_klines(
                    keys.api_key_encrypted, keys.api_secret_encrypted,
                    symbol=symbol, interval="1m", limit=1
                )
                if klines:
                    df = pd.DataFrame(klines, columns=[
                        'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                        'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
                        'taker_buy_quote', 'ignore'
                    ])
                    df['close'] = df['close'].astype(float)
                    
                    market_data = {symbol: df}
                    await self.strategy_manager.update_trailing_stops([deal], market_data, session, client)
                    await self.strategy_manager.check_strategy_exit_signals([deal], market_data, session, client)
            except Exception as e:
                print(f"Ошибка при использовании StrategyManager: {e}")

    async def create_stop_loss_order(
        self,
        deal,
        session,
        client,
        stop_loss_price: float
    ) -> str:
        """Создает ордер стоп лосса на Binance"""
        symbol_str = (
            deal.symbol.value
            if hasattr(deal.symbol, "value")
            else deal.symbol
        )
        
        # Определяем сторону для стоп лосса
        stop_side = 'SELL' if deal.side == 'BUY' else 'BUY'
        
        try:
            print(f"➡️ Отправка ордера STOP_MARKET: symbol={symbol_str}, side={stop_side}, quantity={deal.size}, stopPrice={stop_loss_price:.4f}")
            # Создаем стоп-маркет ордер
            stop_order = await client.futures_create_order(
                symbol=symbol_str,
                side=stop_side,
                type='STOP_MARKET',
                quantity=deal.size,
                stopPrice=stop_loss_price,
                reduceOnly=True
            )
            
            stop_loss_order_id = str(stop_order['orderId'])
            print(f"Создан стоп-лосс ордер: {stop_loss_order_id} по цене {stop_loss_price}")
            
            # Сохраняем ID ордера в базе
            await self.repo.update_stop_loss_order_id(deal.id, stop_loss_order_id, session)
            await session.commit()
            
            return stop_loss_order_id
            
        except Exception as e:
            print(f"❌ Ошибка при создании стоп-лосс ордера на Binance: {e}. Параметры: symbol={symbol_str}, side={stop_side}, quantity={deal.size}, stopPrice={stop_loss_price:.4f}")
            raise

    async def update_stop_loss_order(
        self,
        deal,
        session,
        client,
        new_stop_loss_price: float
    ) -> str:
        """Обновляет существующий ордер стоп лосса на Binance"""
        if not deal.stop_loss_order_id:
            # Если ордера стоп лосса нет, создаем новый
            return await self.create_stop_loss_order(deal, session, client, new_stop_loss_price)
        
        symbol_str = (
            deal.symbol.value
            if hasattr(deal.symbol, "value")
            else deal.symbol
        )
        
        try:
            # Отменяем старый ордер
            await client.futures_cancel_order(
                symbol=symbol_str,
                orderId=int(deal.stop_loss_order_id)
            )
            print(f"Отменен старый стоп-лосс ордер: {deal.stop_loss_order_id}")
            
            # Создаем новый ордер
            new_order_id = await self.create_stop_loss_order(deal, session, client, new_stop_loss_price)
            
            return new_order_id
            
        except Exception as e:
            print(f"Ошибка при обновлении стоп-лосс ордера: {e}")
            # Если не удалось обновить ордер, создаем новый
            return await self.create_stop_loss_order(deal, session, client, new_stop_loss_price)

    async def cancel_stop_loss_order(
        self,
        deal,
        session,
        client
    ):
        """Отменяет ордер стоп лосса на Binance"""
        if not deal.stop_loss_order_id:
            return
            
        symbol_str = (
            deal.symbol.value
            if hasattr(deal.symbol, "value")
            else deal.symbol
        )
        
        try:
            await client.futures_cancel_order(
                symbol=symbol_str,
                orderId=int(deal.stop_loss_order_id)
            )
            print(f"Отменен стоп-лосс ордер: {deal.stop_loss_order_id}")
            
            # Очищаем ID ордера в базе
            await self.repo.update_stop_loss_order_id(deal.id, None, session)
            await session.commit()
            
        except Exception as e:
            print(f"Ошибка при отмене стоп-лосс ордера: {e}")
            # Даже если не удалось отменить на бирже, очищаем в базе
            await self.repo.update_stop_loss_order_id(deal.id, None, session)
            await session.commit()

    async def check_stop_loss_order_status(
        self,
        deal,
        session,
        client
    ) -> bool:
        if not deal.stop_loss_order_id:
            return False
            
        symbol_str = (
            deal.symbol.value
            if hasattr(deal.symbol, "value")
            else deal.symbol
        )
        
        try:
            order_info = await client.futures_get_order(
                symbol=symbol_str,
                orderId=int(deal.stop_loss_order_id)
            )
            
            status = order_info.get('status')
            print(f"Статус стоп-лосс ордера {deal.stop_loss_order_id}: {status}")
            
            if status == 'FILLED':
                # Стоп лосс исполнен - закрываем сделку
                avg_price = float(order_info.get('avgPrice', 0))
                executed_qty = float(order_info.get('executedQty', 0))
                
                # Рассчитываем PnL
                if deal.side == 'BUY':
                    pnl = (avg_price - deal.entry_price) * executed_qty
                else:
                    pnl = (deal.entry_price - avg_price) * executed_qty
                
                print(f"Стоп-лосс исполнен! Цена: {avg_price}, PnL: {pnl:.2f}")
                
                await self.repo.close_deal(
                    deal.id,
                    session=session,
                    pnl=pnl,
                    exit_price=avg_price
                )
                
                if self.log_service:
                    strategy_name = await self._get_strategy_name(deal)
                    await self.log_service.add_log(
                        StrategyLogCreate(
                            user_id=deal.user_id,
                            deal_id=deal.id,
                            strategy=strategy_name,
                            signal="stop_loss_executed",
                            comment=f"Стоп-лосс исполнен на Binance. Цена выхода: {avg_price}, PnL: {pnl:.2f}"
                        ),
                        session=session,
                        autocommit=False
                    )
                
                await session.commit()
                return True
                
            elif status in ['CANCELED', 'EXPIRED', 'REJECTED']:
                # Ордер отменен/просрочен - очищаем ID
                print(f"Стоп-лосс ордер {status.lower()}, очищаем ID")
                await self.repo.update_stop_loss_order_id(deal.id, None, session)
                await session.commit()
                
        except Exception as e:
            print(f"Ошибка при проверке статуса стоп-лосс ордера: {e}")
            
        return False

    async def close_deal_manually(self, deal_id: int, session, apikeys_service):
        deal = await self.repo.get_by_id(deal_id, session)
        if not deal or deal.status != 'open':
            raise HTTPException(
                status_code=404,
                detail="Открытая сделка не найдена"
            )

        keys = await apikeys_service.get_decrypted_by_user(deal.user_id)
        keys = keys[0] if keys else None
        if not keys:
            raise HTTPException(
                status_code=400,
                detail="Нет API-ключей для пользователя"
            )

        client = await self.binance_client.create(
            keys.api_key_encrypted, keys.api_secret_encrypted
        )
        try:
            if deal.stop_loss_order_id:
                await self.cancel_stop_loss_order(deal, session, client)
                print(f"Стоп-лосс ордер отменен для сделки {deal.id}")
            
            positions = await client.futures_position_information(
                symbol=deal.symbol
            )
            position_amt = 0.0
            for pos in positions:
                if pos['symbol'] == deal.symbol:
                    position_amt = float(pos['positionAmt'])
                    break

            print(f"[MANUAL CLOSE] Остаток позиции на Binance: {position_amt}")

            deal_is_long = deal.side == 'BUY'
            position_is_long = position_amt > 0
            position_is_short = position_amt < 0

            if (
                abs(position_amt) < 1e-8
                or (deal_is_long and position_is_short)
                or (not deal_is_long and position_is_long)
            ):
                print(f"Позиция уже закрыта или реверсирована, сделка {deal.id} закрывается только в базе")
                await self.repo.close_deal(deal.id, session)
                if self.log_service:
                    strategy_name = await self._get_strategy_name(deal)
                    await self.log_service.add_log(
                        StrategyLogCreate(
                            deal_id=deal.id,
                            user_id=deal.user_id,
                            strategy=strategy_name,
                            signal="manual_close",
                            comment="Сделка закрыта вручную пользователем. На бирже уже не было позиции по данному направлению (позиция отсутствует/реверсирована)."
                        ),
                        session=session,
                        autocommit=False
                    )
                await session.commit()
                return {
                    "detail":
                        f"Сделка {deal.id} закрыта\
                            (позиция отсутствует/реверсирована на бирже)"
                }

            close_side = 'SELL' if deal_is_long else 'BUY'
            closing_order = await client.futures_create_order(
                symbol=deal.symbol,
                side=close_side,
                type='MARKET',
                quantity=abs(position_amt),
                reduceOnly=True
            )
            exit_price = float(
                closing_order.get("avgPrice")
                or closing_order.get("price")
                or 0.0
            )
            pnl = (
                (exit_price - deal.entry_price) * deal.size if deal_is_long
                else (deal.entry_price - exit_price) * deal.size
            )
            await self.repo.close_deal(
                deal.id,
                session=session,
                pnl=pnl,
                exit_price=exit_price
            )
            if self.log_service:
                strategy_name = await self._get_strategy_name(deal)
                await self.log_service.add_log(
                    StrategyLogCreate(
                        user_id=deal.user_id,
                        deal_id=deal.id,
                        strategy=strategy_name,
                        signal="manual_close",
                        comment=f"Сделка закрыта вручную пользователем через reduceOnly. Цена выхода: {exit_price}, PnL: {pnl:.2f}"
                    ),
                    session=session,
                    autocommit=False
                )
            await session.commit()
            return {
                "detail":
                    f"Сделка {deal.id} закрыта на бирже,\
                        exit={exit_price}, PnL={pnl:.2f}"
            }
        finally:
            await self.binance_client.close(client)

    async def list_paginated(
        self,
        page: int,
        per_page: int,
        user_id: Optional[UUID] = None
    ):
        offset = (page - 1) * per_page
        items, total = await self.repo.list_paginated(
            offset=offset,
            limit=per_page,
            user_id=user_id
        )
        return items, total
