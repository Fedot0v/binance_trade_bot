from sqlalchemy import select, update

from app.repositories.base_repository import BaseRepository
from app.models import APIKeys


class APIKeysRepository(BaseRepository):
    async def add(
        self,
        encrypted_key: str,
        encrypted_secret: str,
        is_active: bool = True
    ):
        record = APIKeys(
            api_key_encrypted=encrypted_key,
            api_secret_encrypted=encrypted_secret,
            is_active=is_active
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_active(self):
        result = await self.db.execute(
            select(APIKeys)
            .where(APIKeys.is_active is True)
            .order_by(APIKeys.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def deactivate_by_id(self, id_: int):
        await self.db.execute(
            update(APIKeys)
            .where(APIKeys.id == id_)
            .values(is_active=False)
        )
        await self.db.flush()
