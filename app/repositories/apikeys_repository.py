from uuid import UUID

from sqlalchemy import select, update, delete

from repositories.base_repository import BaseRepository
from models.trade_models import APIKeys


class APIKeysRepository(BaseRepository):
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
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_active(self, user_id: UUID):
        result = await self.db.execute(
            select(APIKeys)
            .where(APIKeys.is_active.is_(True), APIKeys.user_id == user_id)
            .order_by(APIKeys.created_at.desc()).limit(1)
        )
        return result.scalars().all()

    async def deactivate_by_id(self, id_: int, user_id: UUID):
        await self.db.execute(
            update(APIKeys)
            .where(APIKeys.id == id_, APIKeys.user_id == user_id)
            .values(is_active=False)
        )
        await self.db.flush()
        
    async def get_by_user(self, user_id: UUID):
        result = await self.db.execute(
            select(APIKeys).where(
                APIKeys.user_id == user_id,
                APIKeys.is_active is True
            )
        )
        return result.scalars().all()

    async def delete_for_user(self, apikey_id: int, user_id: UUID):
        await self.db.execute(
            delete(APIKeys)
            .where(APIKeys.id == apikey_id, APIKeys.user_id == user_id)
        )
        await self.db.flush()
