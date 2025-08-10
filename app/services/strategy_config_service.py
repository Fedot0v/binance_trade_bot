from fastapi import HTTPException

from repositories.strategy_config_repository import (
    StrategyConfigRepository
)
from schemas.strategy_config import (
    StrategyConfigCreate,
    StrategyConfigUpdate,
    StrategyConfigRead
)
from strategies.registry import REGISTRY


class StrategyConfigService:
    def __init__(self, repo: StrategyConfigRepository):
        self.repo = repo

    async def get_by_id(self, config_id: int) -> StrategyConfigRead | None:
        try:
            result = await self.repo.get_by_id(config_id)
            return (
                StrategyConfigRead.model_validate(result)
                if result
                else None
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении конфигурации стратегии с ID\
                    {config_id}: {str(e)}"
            )

    async def get_active(self) -> list[StrategyConfigRead]:
        try:
            configs = await self.repo.get_active_configs()
            return [StrategyConfigRead.model_validate(cfg) for cfg in configs]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении активных \
                    конфигураций стратегии: {str(e)}"
            )

    async def create(
        self,
        data: StrategyConfigCreate,
        session,
        autocommit: bool = True
    ) -> StrategyConfigRead:
        try:
            result = await self.repo.add(**data.model_dump())
            if autocommit:
                await session.commit()
            return StrategyConfigRead.model_validate(result)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при создании конфигурации стратегии: {str(e)}"
            )

    async def update(
        self,
        config_id: int,
        data: StrategyConfigUpdate,
        session,
        autocommit: bool = True
    ) -> StrategyConfigRead | None:
        try:
            await self.repo.update_by_id(
                config_id,
                **data.model_dump(exclude_none=True)
            )
            if autocommit:
                await session.commit()
            updated = await self.repo.get_by_id(config_id)
            return (
                StrategyConfigRead.model_validate(updated)
                if updated
                else None
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при обновлении конфигурации \
                    стратегии с ID {config_id}: {str(e)}"
                )

    async def get_parameters(self, config_id: int) -> dict | None:
        try:
            return await self.repo.get_parameters_by_id(config_id)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении параметров \
                    конфигурации стратегии с ID {config_id}: {str(e)}"
                )

    async def get_all_ids(self) -> list[int]:
        try:
            return await self.repo.get_all_ids()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении всех ID\
                    конфигураций стратегии: {str(e)}"
            )
    
    async def sync_from_registry(self, session, autocommit: bool = True):
        """Создать/обновить стратегии в БД из кодового реестра."""
        try:
            for key, meta in REGISTRY.items():
                await self.repo.upsert_by_name(
                    name=key,
                    description=meta.get("description", key),
                    is_active=bool(meta.get("is_active", True)),
                    parameters=meta.get("default_parameters", {}) or {}
                )
            if autocommit:
                await session.commit()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка синхронизации стратегий: {str(e)}"
            )

    async def seed_from_registry_if_missing(
        self,
        session,
        autocommit: bool = True
    ):
        try:
            for key, meta in REGISTRY.items():
                await self.repo.ensure_exists_by_name(
                    name=key,
                    description=meta.get("description", key),
                    is_active=bool(meta.get("is_active", True)),
                    parameters=meta.get("default_parameters", {}) or {}
                )
            if autocommit:
                await session.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка инициализации стратегий: {str(e)}")
