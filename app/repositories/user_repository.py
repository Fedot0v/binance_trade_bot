from typing import Sequence, Optional

from sqlalchemy import select, update, delete

from repositories.base_repository import BaseRepository
from models.user_model import UserStrategyTemplate, User
from models.trade_models import StrategyConfig


class UserStrategyTemplateRepository(BaseRepository):
    async def add(self, user_id: int, **kwargs):
        template = UserStrategyTemplate(user_id=user_id, **kwargs)
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def get_all(self, user_id: int) -> Sequence[UserStrategyTemplate]:
        result = await self.db.execute(
            select(UserStrategyTemplate)
            .where(UserStrategyTemplate.user_id == user_id)
        )
        return result.scalars().all()

    async def get_by_id(self, id_: int, user_id: int):
        result = await self.db.execute(
            select(UserStrategyTemplate).where(
                UserStrategyTemplate.id == id_,
                UserStrategyTemplate.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def update_by_id(self, id_: int, user_id: int, **kwargs):
        await self.db.execute(
            update(UserStrategyTemplate)
            .where(
                UserStrategyTemplate.id == id_,
                UserStrategyTemplate.user_id == user_id
            )
            .values(**kwargs)
        )
        await self.db.flush()

    async def delete_by_id(self, id_: int, user_id: int):
        await self.db.execute(
            delete(UserStrategyTemplate)
            .where(
                UserStrategyTemplate.id == id_,
                UserStrategyTemplate.user_id == user_id
            )
        )
        await self.db.flush()
        
    async def get_active(self, user_id):
        result = await self.db.execute(
            select(UserStrategyTemplate)
            .where(UserStrategyTemplate.user_id == user_id)
            .where(UserStrategyTemplate.is_active.is_(True)
        )
        return result.scalar_one_or_none()
        
    async def set_active(self, user_id: int, template_id: int):
        await self.db.execute(
            update(UserStrategyTemplate)
            .where(UserStrategyTemplate.user_id == user_id)
            .values(is_active=False)
        )
        await self.db.execute(
            update(UserStrategyTemplate)
            .where(
                UserStrategyTemplate.user_id == user_id,
                UserStrategyTemplate.id == template_id
            )
            .values(is_active=True)
        )
        await self.db.flush()
