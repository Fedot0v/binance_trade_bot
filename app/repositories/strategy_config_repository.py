from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from models.trade_models import StrategyConfig


class StrategyConfigRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(
        self,
        name: str,
        description: str,
        is_active: bool,
        parameters: dict
    ):
        strategy = StrategyConfig(
            name=name,
            description=description,
            is_active=is_active,
            parameters=parameters
        )
        self.db.add(strategy)
        await self.db.flush()
        await self.db.refresh(strategy)
        return strategy

    async def update_by_id(self, config_id: int, **kwargs):
        await self.db.execute(
            update(StrategyConfig)
            .where(StrategyConfig.id == config_id)
            .values(**kwargs)
        )
        await self.db.flush()

    async def delete_by_id(self, config_id: int):
        await self.db.execute(
            delete(StrategyConfig)
            .where(StrategyConfig.id == config_id)
        )
        await self.db.flush()

    async def get_by_id(self, config_id: int) -> StrategyConfig | None:
        result = await self.db.execute(
            select(StrategyConfig).where(StrategyConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_active_configs(self) -> list[StrategyConfig]:
        result = await self.db.execute(
            select(StrategyConfig)
            .where(StrategyConfig.is_active.is_(True))
        )
        return result.scalars().all()
    
    async def get_parameters_by_id(self, config_id: int) -> dict | None:
        strategy = await self.get_by_id(config_id)
        return strategy.parameters if strategy else None

    async def get_all_ids(self) -> list[int]:
        result = await self.db.execute(
            select(StrategyConfig.id)
        )
        return [row[0] for row in result.all()]
