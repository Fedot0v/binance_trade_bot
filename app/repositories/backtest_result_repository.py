from typing import List, Type, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.backtest_result_model import BacktestResultModel
from repositories.base_repository import BaseRepository

class BacktestResultRepository(BaseRepository[BacktestResultModel]):
    """Repository for managing backtest results."""
    def __init__(self, session: AsyncSession):
        super().__init__(session, BacktestResultModel)

    async def create_backtest_result(
        self,
        task_id: str,
        template_id: int,
        user_id: UUID,
        status: str = "pending",
        results: Optional[dict] = None
    ) -> BacktestResultModel:
        new_result = BacktestResultModel(
            task_id=task_id,
            template_id=template_id,
            user_id=user_id,
            status=status,
            results=results
        )
        self.session.add(new_result)
        await self.session.flush()
        return new_result

    async def get_by_task_id(self, task_id: str) -> Optional[BacktestResultModel]:
        stmt = select(self.model).where(self.model.task_id == task_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_backtest_status(
        self,
        task_id: str,
        status: str,
        results: Optional[dict] = None
    ) -> Optional[BacktestResultModel]:
        backtest_result = await self.get_by_task_id(task_id)
        if backtest_result:
            backtest_result.status = status
            if results is not None:
                backtest_result.results = results
            if status == "completed" or status == "failed":
                backtest_result.completed_at = datetime.utcnow()
            await self.session.flush()
        return backtest_result

    async def get_all_by_user(self, user_id: UUID) -> List[BacktestResultModel]:
        stmt = select(self.model).where(self.model.user_id == user_id).order_by(desc(self.model.created_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_paginated_by_user(
        self,
        user_id: UUID,
        offset: int,
        limit: int
    ) -> tuple[List[BacktestResultModel], int]:
        query = select(self.model).where(self.model.user_id == user_id)
        total_query = select(func.count()).where(self.model.user_id == user_id).select_from(self.model)

        total_result = await self.session.execute(total_query)
        total_count = total_result.scalar_one()

        paginated_query = query.order_by(desc(self.model.created_at)).offset(offset).limit(limit)
        results = await self.session.execute(paginated_query)
        items = list(results.scalars().all())

        return items, total_count
