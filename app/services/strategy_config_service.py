from app.repositories.strategy_config_repository import (
    StrategyConfigRepository
)
from app.schemas.strategy_config import (
    StrategyConfigCreate,
    StrategyConfigUpdate,
    StrategyConfigRead
)


class StrategyConfigService:
    def __init__(self, repo: StrategyConfigRepository):
        self.repo = repo

    async def get_by_id(self, config_id: int) -> StrategyConfigRead | None:
        result = await self.repo.get_by_id(config_id)
        return StrategyConfigRead.model_validate(result) if result else None

    async def get_active(self) -> list[StrategyConfigRead]:
        configs = await self.repo.get_active_configs()
        return [StrategyConfigRead.model_validate(cfg) for cfg in configs]

    async def create(self, data: StrategyConfigCreate, session) -> StrategyConfigRead:
        result = await self.repo.add(**data.model_dump())
        await session.commit()
        return StrategyConfigRead.model_validate(result)

    async def update(self, config_id: int, data: StrategyConfigUpdate, session) -> StrategyConfigRead | None:
        await self.repo.update_by_id(config_id, **data.model_dump(exclude_none=True))
        await session.commit()
        updated = await self.repo.get_by_id(config_id)
        return StrategyConfigRead.model_validate(updated) if updated else None
