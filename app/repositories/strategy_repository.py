from sqlalchemy import select, func

from models.trade_models import StrategyLog


class StrategyLogRepository:
    def __init__(self, db=None):
        self.db = db

    async def add(
        self,
        user_id,
        deal_id,
        strategy,
        signal,
        comment=None,
        session=None
    ):
        session = session or self.db
        if session is None:
            raise ValueError("Session must be provided either via parameter or repository init.")

        record = StrategyLog(
            user_id=user_id,
            deal_id=deal_id,
            strategy=strategy,
            signal=signal,
            comment=comment
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        return record

    async def get_by_deal(self, deal_id):
        result = await self.db.execute(
            select(StrategyLog).where(StrategyLog.deal_id == deal_id)
        )
        return result.scalars().all()

    async def get_last_logs(self, limit=10):
        result = await self.db.execute(
            select(StrategyLog).order_by(StrategyLog.id.desc()).limit(limit)
        )
        return result.scalars().all()

    async def get_by_user(self, user_id, offset=0, limit=100):
        stmt = select(StrategyLog).where(StrategyLog.user_id == user_id)
        total_stmt = (
            select(func.count())
            .select_from(StrategyLog)
            .where(StrategyLog.user_id == user_id)
        )
        stmt = stmt.order_by(StrategyLog.id.desc()).offset(offset).limit(limit)
        
        items = (await self.db.execute(stmt)).scalars().all()
        total = (await self.db.execute(total_stmt)).scalar_one()

        return items, total
