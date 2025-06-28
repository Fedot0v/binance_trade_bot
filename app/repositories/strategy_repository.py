from sqlalchemy import select

from app.repositories.base_repository import BaseRepository
from app.models import StrategyLog


class StrategyLogRepository(BaseRepository):
    async def add(
        self,
        strategy: str,
        signal: str,
        comment: str = '',
        deal_id: int = None
    ):
        log = StrategyLog(
            strategy=strategy,
            signal=signal,
            comment=comment,
            deal_id=deal_id
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def get_logs_by_deal_id(self, deal_id: int):
        result = await self.db.execute(
            select(StrategyLog)
            .where(StrategyLog.deal_id == deal_id)
        )
        return result.scalars().all()
