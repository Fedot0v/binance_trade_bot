from fastapi import HTTPException, Depends

from repositories.deal_repository import DealRepository
from schemas.deal import DealCreate, DealRead, DealDelete
from encryption.crypto import decrypt
from schemas.strategy_log import StrategyLogCreate


class DealService:
    def __init__(
        self,
        repo: DealRepository,
        binance_client=None,
        apikeys_service=None,
        log_service=None
    ):
        self.repo = repo
        self.binance_client = binance_client
        self.apikeys_service = apikeys_service
        self.log_service = log_service

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

        print(
            f"API-ключ найден для user_id={deal.user_id},\
                создаём бинанс-клиент"
        )
        client = await self.binance_client.create(
            keys.api_key_encrypted, keys.api_secret_encrypted, testnet=True
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
                order_id={deal.order_id}"
        )
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
            await self.repo.close_deal(deal.id, session)
            await session.commit()
            print(
                f"Сделка {deal.id} помечена как закрытая (по статусу Binance)"
            )
            return

        await self._update_stop_loss_if_needed(deal, session, client)

    async def _update_stop_loss_if_needed(
        self,
        deal,
        session,
        client,
        log_service=None,
        strategy_name=""
    ):
        print(
            f"Проверка стоп-лосса по сделке {deal.id}:\
                entry_price={deal.entry_price},\
                    стоп={deal.stop_loss}, side={deal.side}"
        )
        price = await self._get_current_mark_price(client, deal.symbol)
        print(f"Текущая mark price: {price}")

        updated, new_stop, stop_dir = await self._trailing_stop_update(
            deal,
            session,
            price
        )

        if updated:
            print(f"[TRAILING] Стоп-лосс обновлён: {new_stop:.4f} ({stop_dir})")
        else:
            print(f"[TRAILING] Стоп-лосс не изменился")

        stop_loss_price = self._calculate_absolute_stop_loss(deal)
        print(f"Рассчитан абсолютный stop_loss_price: {stop_loss_price}")

        if self._is_stop_loss_triggered(deal, price, stop_loss_price):
            print(
                f"СТОП-ЛОСС СРАБОТАЛ! side={deal.side},\
                    price={price}, stop_loss_price={stop_loss_price}"
            )
            await self._close_deal_on_stop_loss(
                deal,
                session,
                client,
                price,
                stop_loss_price,
                strategy_name
            )

    async def _get_current_mark_price(self, client, symbol):
        price_info = await client.futures_mark_price(symbol=symbol)
        return round(float(price_info["markPrice"]), 2)

    async def _trailing_stop_update(self, deal, session, price):
        updated = False
        if deal.side == 'BUY':
            max_price = getattr(deal, 'max_price', None) or deal.entry_price
            if price > max_price:
                print(
                    f"[TRAILING] Новый максимум для лонга:\
                        {price} (старый: {max_price})"
                )
                max_price = price
                await self.repo.update_max_price(deal.id, max_price, session)
                updated = True
            else:
                print(f"[TRAILING] Максимум для лонга не изменился: {max_price}")
            new_stop = max_price * 0.998
            stop_dir = "ниже max"
        else:
            min_price = getattr(deal, 'min_price', None) or deal.entry_price
            if price < min_price:
                print(
                    f"[TRAILING] Новый минимум для шорта: {price}\
                        (старый: {min_price})"
                )
                min_price = price
                await self.repo.update_min_price(deal.id, min_price, session)
                updated = True
            else:
                print(
                    f"[TRAILING] Минимум для шорта не изменился: {min_price}"
                )
            new_stop = min_price * 1.002
            stop_dir = "выше min"

        if updated:
            await self.repo.update_stop_loss(deal.id, new_stop, session)
            await session.commit()
        return updated, new_stop, stop_dir

    def _calculate_absolute_stop_loss(self, deal):
        if isinstance(deal.stop_loss, float) and deal.stop_loss < 1:
            if not deal.entry_price:
                print(
                    f"entry_price отсутствует,\
                        расчет стоп-лосса невозможен для сделки {deal.id}"
                )
                return 0
            return (
                deal.entry_price * (1 - deal.stop_loss) if deal.side == 'BUY'
                else deal.entry_price * (1 + deal.stop_loss)
            )
        else:
            return deal.stop_loss

    def _is_stop_loss_triggered(self, deal, price, stop_loss_price):
        return (
            deal.side == 'BUY' and price <= stop_loss_price or
            deal.side == 'SELL' and price >= stop_loss_price
        )

    async def _close_deal_on_stop_loss(
        self,
        deal,
        session,
        client,
        price,
        stop_loss_price,
        strategy_name
    ):
        positions = await client.futures_position_information(
            symbol=deal.symbol
        )
        position_amt = 0.0
        for pos in positions:
            if pos['symbol'] == deal.symbol:
                position_amt = float(pos['positionAmt'])
                break

        print(f"[STOP-LOSS] Остаток позиции на Binance: {position_amt}")

        deal_is_long = deal.side == 'BUY'
        position_is_long = position_amt > 0
        position_is_short = position_amt < 0
        mark_price = await self._get_current_mark_price(client, deal.symbol)
        exit_price = mark_price
        pnl = (
            (exit_price - deal.entry_price) * deal.size if deal_is_long
            else (deal.entry_price - exit_price) * deal.size
        )
        if (
            abs(position_amt) < 1e-8
            or (deal_is_long and position_is_short)
            or (not deal_is_long and position_is_long)
        ):
            print(
                f"Позиция уже закрыта или реверсирована на бирже,\
                    сделка {deal.id} закрывается только в базе"
            )
            
            await self.repo.close_deal(
                deal.id,
                session=session,
                pnl=pnl,
                exit_price=exit_price
            )
            if self.log_service:
                await self.log_service.add_log(
                    StrategyLogCreate(
                        user_id=deal.user_id,
                        deal_id=deal.id,
                        strategy=strategy_name or "Auto",
                        signal="stop_loss",
                        comment=f"Сделка закрыта по стоп-лоссу без ордера на биржу (позиция отсутствует/реверсирована). Цена выхода: {exit_price}, PnL: {pnl:.2f}"
                    ),
                    session=session,
                    autocommit=False
                )
            await session.commit()
            return

        close_side = 'SELL' if deal_is_long else 'BUY'
        closing_order = await client.futures_create_order(
            symbol=deal.symbol,
            side=close_side,
            type='MARKET',
            quantity=abs(position_amt),
            reduceOnly=True
        )
        print(f"Сделка закрыта по стопу: exit_price={exit_price}, PnL={pnl}")
        await self.repo.close_deal(
            deal.id,
            session=session,
            pnl=pnl,
            exit_price=exit_price
        )
        if self.log_service:
            await self.log_service.add_log(
                StrategyLogCreate(
                    user_id=deal.user_id,
                    deal_id=deal.id,
                    strategy=strategy_name or "Auto",
                    signal="stop_loss",
                    comment=f"Сделка закрыта по стоп-лоссу. Цена выхода: {exit_price}, PnL: {pnl:.2f}"
                ),
                session=session,
                autocommit=False
            )
        await session.commit()
        print(f"Сделка {deal.id} закрыта в базе и коммитнута")
        

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
            keys.api_key_encrypted, keys.api_secret_encrypted, testnet=True
        )
        try:
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
                    await self.log_service.add_log(
                        StrategyLogCreate(
                            deal_id=deal.id,
                            user_id=deal.user_id,
                            strategy=(
                                deal.template.template_name
                                if deal.template
                                else "Auto"
                            ),
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
                await self.log_service.add_log(
                    StrategyLogCreate(
                        user_id=deal.user_id,
                        deal_id=deal.id,
                        strategy=(
                            deal.template.template_name
                            if deal.template
                            else "Auto"
                        ),
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
