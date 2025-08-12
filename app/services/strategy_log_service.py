from fastapi import HTTPException

from repositories.strategy_repository import StrategyLogRepository
from schemas.strategy_log import StrategyLogCreate, StrategyLogRead


class StrategyLogService:
    def __init__(self, repo: StrategyLogRepository):
        self.repo = repo

    async def add_log(
        self,
        data: StrategyLogCreate,
        session=None,
        autocommit: bool = True
    ) -> StrategyLogRead:
        try:
            record = await self.repo.add(
                user_id=data.user_id,
                deal_id=data.deal_id,
                strategy=data.strategy,
                signal=data.signal,
                comment=data.comment,
                session=session
            )
            if autocommit and session is not None:
                await session.commit()
            return StrategyLogRead.model_validate(record)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при добавлении лога стратегии: {str(e)}"
            )

    async def get_logs_by_deal(self, deal_id) -> list[StrategyLogRead]:
        try:
            records = await self.repo.get_by_deal(deal_id)
            return [StrategyLogRead.model_validate(r) for r in records]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении логов стратегии \
                    для сделки с ID {deal_id}: {str(e)}"
            )

    async def get_last_logs(self, limit=10) -> list[StrategyLogRead]:
        try:
            records = await self.repo.get_last_logs(limit)
            return [StrategyLogRead.model_validate(r) for r in records]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении последних логов стратегии: {str(e)}"
            )

    async def get_logs_by_user(
        self,
        user_id,
        page,
        per_page
    ) -> list[StrategyLogRead]:
        offset = (page - 1) * per_page
        items, total = await self.repo.get_by_user(user_id, offset, per_page)
        return [StrategyLogRead.model_validate(r) for r in records], total
