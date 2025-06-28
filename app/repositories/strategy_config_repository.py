from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.trade_models import StrategyConfig


class StrategyConfigRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, config_id: int) -> StrategyConfig | None:
        result = await self.db.execute(
            select(StrategyConfig).where(StrategyConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_active_configs(self) -> list[StrategyConfig]:
        result = await self.db.execute(
            select(StrategyConfig)
            .where(StrategyConfig.is_active is True)
        )
        return result.scalars().all()
