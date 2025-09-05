from uuid import UUID

from fastapi import HTTPException

from repositories.user_repository import UserStrategyTemplateRepository

from schemas.user_strategy_template import (
    UserStrategyTemplateCreate,
    UserStrategyTemplateUpdate,
    UserStrategyTemplateRead
)
from models.user_model import Symbols, Intervals


class UserStrategyTemplateService:
    def __init__(self, repo: UserStrategyTemplateRepository):
        self.repo = repo

    async def create(
        self,
        data: UserStrategyTemplateCreate,
        user_id: UUID,
        session,
        autocommit: bool = True
    ) -> UserStrategyTemplateRead:
        try:
            data.interval = Intervals(data.interval)
            data.symbol = Symbols(data.symbol)
            result = await self.repo.add(user_id=user_id, **data.model_dump())
            if autocommit:
                await session.commit()
            return UserStrategyTemplateRead.model_validate(result)
        except HTTPException as e:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при создании шаблона стратегии: {str(e)}"
            )

    async def get_by_id(
        self,
        id_: int,
        user_id: UUID
    ) -> UserStrategyTemplateRead | None:
        try:
            result = await self.repo.get_by_id(id_, user_id)
            return UserStrategyTemplateRead.model_validate(result)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении шаблона стратегии с ID {id_}: {str(e)}"
            )

    async def get_all(self, user_id: UUID) -> list[UserStrategyTemplateRead]:
        try:
            results = await self.repo.get_all(user_id)
            return [
                UserStrategyTemplateRead.model_validate(item)
                for item in results
            ]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении всех шаблонов стратегии для пользователя {user_id}: {str(e)}"
            )

    async def update(
        self,
        id_: int,
        data: UserStrategyTemplateUpdate,
        user_id: UUID,
        session,
        autocommit: bool = True
    ) -> UserStrategyTemplateRead | None:
        try:
            data.interval = Intervals(data.interval)
            data.symbol = Symbols(data.symbol)
            await self.repo.update_by_id(
                id_,
                user_id=user_id,
                **data.model_dump(exclude_none=True)
            )
            if autocommit:
                await session.commit()
            updated = await self.repo.get_by_id(id_, user_id)
            return UserStrategyTemplateRead.model_validate(updated)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при обновлении шаблона стратегии с ID {id_}: {str(e)}"
            )

    async def delete(
        self,
        id_: int,
        user_id: UUID,
        session,
        autocommit: bool = True
    ):
        try:
            deleted = await self.repo.delete_by_id(id_, user_id)
            if autocommit:
                await session.commit()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при удалении шаблона стратегии с ID {id_}: {str(e)}"
            )

    async def get_active_strategie(self, user_id) -> list:
        try:
            strategie = await self.repo.get_active(user_id)
            return strategie
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении активных стратегий: {str(e)}"
            )
    
    async def set_active(
        self,
        user_id: UUID,
        template_id: int,
        session,
        autocommit: bool = True
    ):
        try:
            await self.repo.set_active(user_id, template_id)
            if autocommit:
                await session.commit()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при активации шаблона: {str(e)}"
            )
