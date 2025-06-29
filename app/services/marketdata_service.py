from app.repositories.marketdata_repository import MarketDataRepository
from app.schemas.market_data import MarketDataCreate, MarketDataRead


class MarketDataService:
    def __init__(self, repo: MarketDataRepository):
        self.repo = repo

    async def add_many(self, data: list[MarketDataCreate], session) -> list[MarketDataRead]:
        records = await self.repo.add_many([d.model_dump() for d in data])
        await session.commit()
        return [MarketDataRead.model_validate(r) for r in records]

    async def get_latest(self, symbol: str, limit: int = 100):
        records = await self.repo.get_latest(symbol, limit)
        return [MarketDataRead.model_validate(r) for r in records]
