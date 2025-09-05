from uuid import UUID

from sqlalchemy import select, update, delete

from repositories.base_repository import BaseRepository
from models.trade_models import APIKeys


class APIKeysRepository(BaseRepository[APIKeys]):
    def __init__(self, session):
        super().__init__(session, APIKeys)

    async def add(
        self,
        user_id: UUID,
        encrypted_key: str,
        encrypted_secret: str,
        is_active: bool = True
    ):
        record = APIKeys(
            user_id=user_id,
            api_key_encrypted=encrypted_key,
            api_secret_encrypted=encrypted_secret,
            is_active=is_active
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_active(self, user_id: UUID):
        result = await self.session.execute(
            select(self.model)
            .where(self.model.is_active.is_(True), self.model.user_id == user_id)
            .order_by(self.model.created_at.desc()).limit(1)
        )
        return result.scalars().all()

    async def deactivate_by_id(self, id_: int, user_id: UUID):
        await self.session.execute(
            update(self.model)
            .where(self.model.id == id_, self.model.user_id == user_id)
            .values(is_active=False)
        )
        await self.session.flush()
        
    async def get_by_user(self, user_id: UUID):
        result = await self.session.execute(
            select(self.model).where(
                self.model.user_id == user_id,
                self.model.is_active.is_(True)
            )
        )
        return result.scalars().all()

    async def delete_for_user(self, apikey_id: int, user_id: UUID):
        await self.session.execute(
            delete(self.model)
            .where(self.model.id == apikey_id, self.model.user_id == user_id)
        )
        await self.session.flush()
