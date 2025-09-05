from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.backtest_result_repository import BacktestResultRepository
from schemas.backtest_result import BacktestResultCreate, BacktestResultRead
from models.backtest_result_model import BacktestResultModel
from celery.result import AsyncResult


class BacktestResultService:
    def __init__(self, repository: BacktestResultRepository):
        """Initializes the BacktestResultService with a repository."""
        self.repository = repository

    async def create_result(
        self,
        task_id: str,
        template_id: int,
        user_id: UUID
    ) -> BacktestResultRead:
        new_result = await self.repository.create_backtest_result(
            task_id=task_id,
            template_id=template_id,
            user_id=user_id,
            status="pending"
        )
        await self.repository.session.commit()
        return BacktestResultRead.model_validate(new_result)

    async def update_result_status(
        self,
        task_id: str,
        status: str,
        results: Optional[dict] = None
    ) -> Optional[BacktestResultRead]:
        updated_result = await self.repository.update_backtest_status(
            task_id,
            status,
            results
        )
        await self.repository.session.commit()
        return BacktestResultRead.model_validate(updated_result) if updated_result else None

    async def get_result_by_task_id(self, task_id: str) -> Optional[BacktestResultRead]:
        result = await self.repository.get_by_task_id(task_id)
        return BacktestResultRead.model_validate(result) if result else None

    async def get_all_results_by_user(self, user_id: UUID) -> List[BacktestResultRead]:
        results = await self.repository.get_all_by_user(user_id)
        return [BacktestResultRead.model_validate(result) for result in results]

    async def get_paginated_results_by_user(
        self,
        user_id: UUID,
        page: int,
        per_page: int
    ) -> Tuple[List[BacktestResultRead], int]:
        offset = (page - 1) * per_page
        items, total = await self.repository.get_paginated_by_user(
            user_id=user_id,
            offset=offset,
            limit=per_page
        )
        return [BacktestResultRead.model_validate(item) for item in items], total
