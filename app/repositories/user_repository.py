from typing import Sequence, Optional

from sqlalchemy import select, update, delete

from repositories.base_repository import BaseRepository
from models.user_model import UserStrategyTemplate, User
from models.trade_models import StrategyConfig


class UserStrategyTemplateRepository(BaseRepository[UserStrategyTemplate]):
    def __init__(self, session):
        super().__init__(session, UserStrategyTemplate)

    async def add(self, user_id: int, **kwargs):
        template = UserStrategyTemplate(user_id=user_id, **kwargs)
        self.session.add(template)
        await self.session.flush()
        await self.session.refresh(template)
        return template

    async def get_all(self, user_id: int) -> Sequence[UserStrategyTemplate]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
        )
        return result.scalars().all()

    async def get_by_id(self, id_: int, user_id: int):
        result = await self.session.execute(
            select(self.model).where(
                self.model.id == id_,
                self.model.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def update_by_id(self, id_: int, user_id: int, **kwargs):
        await self.session.execute(
            update(self.model)
            .where(
                self.model.id == id_,
                self.model.user_id == user_id
            )
            .values(**kwargs)
        )
        await self.session.flush()

    async def delete_by_id(self, id_: int, user_id: int):
        await self.session.execute(
            delete(self.model)
            .where(
                self.model.id == id_,
                self.model.user_id == user_id
            )
        )
        await self.session.flush()
        
    async def get_active(self, user_id):
        result = await self.session.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .where(self.model.is_active.is_(True))
        )
        return result.scalar_one_or_none()
        
    async def set_active(self, user_id: int, template_id: int):
        await self.session.execute(
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(is_active=False)
        )
        await self.session.execute(
            update(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.id == template_id
            )
            .values(is_active=True)
        )
        await self.session.flush()
