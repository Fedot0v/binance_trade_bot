from sqlalchemy import select, update

from app.repositories.base_repository import BaseRepository
from app.models.trade_models import Deal


class DealRepository(BaseRepository):
    async def add(self, user_id: int, **kwargs):
        deal = Deal(user_id=user_id, **kwargs)
        self.db.add(deal)
        await self.db.flush()
        await self.db.refresh(deal)
        return deal
    
    async def get_all(self):
        result = await self.db.execute(select(Deal))
        return result.scalars().all()

    async def get_open_deals(self, user_id: int):
        result = await self.db.execute(
            select(Deal)
            .where(Deal.status == 'open', Deal.user_id == user_id)
        )
        return result.scalars().all()

    async def close_deal(
        self,
        deal_id: int,
        exit_price: float,
        pnl: float
    ):
        await self.db.execute(
            update(Deal).where(Deal.id == deal_id).values(
                exit_price=exit_price,
                pnl=pnl,
                status='closed'
            )
        )
        await self.db.flush()