from app.repositories.deal_repository import DealRepository
from app.schemas.deal import DealCreate, DealRead


class DealService:
    def __init__(self, repo: DealRepository):
        self.repo = repo

    async def create(self, data: DealCreate, session) -> DealRead:
        result = await self.repo.add(**data.model_dump())
        await session.commit()
        return DealRead.model_validate(result)
    
    async def get_all(self) -> list[DealRead]:
        deals = await self.repo.get_all()
        return [DealRead.model_validate(deal) for deal in deals]

    async def get_open(self):
        deals = await self.repo.get_open_deals()
        return [DealRead.model_validate(deal) for deal in deals]

    async def close(self, deal_id: int, exit_price: float, pnl: float, session):
        await self.repo.close_deal(deal_id, exit_price, pnl)
        await session.commit()
