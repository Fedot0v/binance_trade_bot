from sqlalchemy import select, update

from app.repositories.base_repository import BaseRepository
from app.models import Deal


class DealRepository(BaseRepository):
    async def add(self, **kwargs):
        deal = Deal(**kwargs)
        self.db.add(deal)
        await self.db.flush()
        await self.db.refresh(deal)
        return deal

    async def get_open_deals(self):
        result = await self.db.execute(
            select(Deal)
            .where(Deal.status == 'open')
        )
        return result.scalars().all()

    async def close_deal(self, deal_id: int, exit_price: float, pnl: float):
        await self.db.execute(
            update(Deal).where(Deal.id == deal_id).values(
                exit_price=exit_price,
                pnl=pnl,
                status='closed'
            )
        )
        await self.db.flush()