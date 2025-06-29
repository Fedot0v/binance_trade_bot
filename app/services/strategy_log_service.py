from app.repositories.strategy_repository import StrategyLogRepository
from app.schemas.strategy_log import StrategyLogCreate, StrategyLogRead


class StrategyLogService:
    def __init__(self, repo: StrategyLogRepository):
        self.repo = repo

    async def add(self, data: StrategyLogCreate, session) -> StrategyLogRead:
        result = await self.repo.add(**data.model_dump())
        await session.commit()
        return StrategyLogRead.model_validate(result)

    async def get_by_deal(self, deal_id: int):
        logs = await self.repo.get_logs_by_deal_id(deal_id)
        return [StrategyLogRead.model_validate(log) for log in logs]
