from uuid import UUID
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, desc, delete, func
from sqlalchemy.orm import joinedload

from repositories.base_repository import BaseRepository
from models.trade_models import Deal


class DealRepository(BaseRepository[Deal]):
    def __init__(self, session):
        super().__init__(session, Deal)

    async def add(self, user_id: int, **kwargs):
        deal = Deal(user_id=user_id, **kwargs)
        self.session.add(deal)
        await self.session.flush()
        await self.session.refresh(deal)
        return deal

    async def get_all(self):
        result = await self.session.execute(select(self.model))
        return result.scalars().all()

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        user_id: Optional[UUID] = None
    ):
        stmt = select(self.model)
        total_stmt = select(func.count()).select_from(self.model)

        if user_id is not None:
            stmt = stmt.where(self.model.user_id == user_id)
            total_stmt = total_stmt.where(self.model.user_id == user_id)

        stmt = stmt.order_by(desc(self.model.id)).offset(offset).limit(limit)

        items = (await self.session.execute(stmt)).scalars().all()
        total = (await self.session.execute(total_stmt)).scalar_one()

        return items, total

    async def get_open_deals_for_user(self, user_id: int, symbol):
        result = await self.session.execute(
            select(self.model)
            .where(self.model.status == 'open', self.model.user_id == user_id)
            .where(self.model.symbol == symbol)
        )
        return result.scalars().all()

    async def get_last_deal(self, user_id: int):
        result = await self.session.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(desc(self.model.id))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, deal_id: int, session):
        result = await session.execute(
            select(self.model)
            .options(joinedload(self.model.template))
            .where(self.model.id == deal_id)
        )
        return result.scalar_one_or_none()

    async def get_open_deal_by_symbol(self, user_id: UUID, symbol: str):
        result = await self.session.execute(
            select(self.model)
            .where(
                self.model.status == 'open',
                self.model.user_id == user_id,
                self.model.symbol == symbol
            )
        )
        return result.scalar_one_or_none()

    async def close_deal(
        self,
        deal_id: int,
        exit_price: float = None,
        pnl: float = None,
        session=None
    ):
        values = {
            'status': 'closed',
            'closed_at': datetime.now(),
            'exit_price': exit_price
        }
        if pnl is not None:
            values['pnl'] = pnl
        await session.execute(
            update(self.model)
            .where(self.model.id == deal_id)
            .values(**values)
        )

    async def get_open_deals(self, session):
        result = await session.execute(
            select(self.model).where(self.model.status == 'open')
        )
        return result.scalars().all()

    async def update_stop_loss(self, deal_id, new_stop_loss, session):
        await session.execute(
            update(self.model).where(self.model.id == deal_id)
            .values(stop_loss=new_stop_loss)
        )
        await session.flush()

    async def update_stop_loss_order_id(self, deal_id, stop_loss_order_id, session):
        await session.execute(
            update(self.model).where(self.model.id == deal_id)
            .values(stop_loss_order_id=stop_loss_order_id)
        )
        await session.flush()

    async def get_by_stop_loss_order_id(self, session, stop_loss_order_id):
        result = await session.execute(
            select(self.model).where(self.model.stop_loss_order_id == stop_loss_order_id)
        )
        return result.scalar_one_or_none()

    async def update_deal_from_binance(
        self,
        session,
        deal_id,
        exit_price=None,
        status=None,
        closed_at=None
    ):
        stmt = update(self.model).where(self.model.id == deal_id)
        update_data = {}
        if exit_price is not None:
            update_data['exit_price'] = exit_price
        if status is not None:
            update_data['status'] = status
        if closed_at is not None:
            update_data['closed_at'] = closed_at
        if update_data:
            stmt = stmt.values(**update_data)
            await session.execute(stmt)
            await session.flush()

    async def get_by_order_id(self, session, order_id):
        result = await session.execute(
            select(self.model).where(self.model.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_deals_for_bot(self, session, bot_id):
        result = await session.execute(
            select(self.model).where(self.model.bot_id == bot_id)
        )
        return result.scalars().all()
    
    async def delete_deal(self, deal_id, session):
        await session.execute(
            delete(self.model).where(self.model.id == deal_id)
        )
        await self.session.flush()

    async def update_max_price(self, deal_id, max_price, session):
        await session.execute(
            update(self.model).where(self.model.id == deal_id).values(max_price=max_price)
        )

    async def update_min_price(self, deal_id, min_price, session):
        await session.execute(
            update(self.model).where(self.model.id == deal_id).values(min_price=min_price)
        )
