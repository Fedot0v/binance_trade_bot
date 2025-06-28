from sqlalchemy import select

from app.repositories.base_repository import BaseRepository
from app.models import MarketData


class MarketDataRepository(BaseRepository):
    async def add_many(self, rows: list[dict]):
        records = [MarketData(**row) for row in rows]
        self.db.add_all(records)
        await self.db.flush()
        return records

    async def get_latest(self, symbol: str, limit: int = 100):
        result = await self.db.execute(
            select(MarketData)
            .where(MarketData.symbol == symbol)
            .order_by(MarketData.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()[::-1]
