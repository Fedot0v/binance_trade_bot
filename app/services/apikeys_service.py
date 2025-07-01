from app.repositories.apikeys_repository import APIKeysRepository
from app.schemas.apikey import APIKeysCreate, APIKeysRead
from app.encryption.crypto import encrypt


class APIKeysService:
    def __init__(self, repo: APIKeysRepository):
        self.repo = repo

    async def create(self, data: APIKeysCreate, session) -> APIKeysRead:
        encrypted_key = encrypt(data.api_key)
        encrypted_secret = encrypt(data.api_secret)
        result = await self.repo.add(
            encrypted_key,
            encrypted_secret,
            data.is_active
        )
        await session.commit()
        return APIKeysRead.model_validate(result)

    async def get_active(self) -> APIKeysRead | None:
        record = await self.repo.get_active()
        return APIKeysRead.model_validate(record) if record else None

    async def deactivate(self, id_: int, session):
        await self.repo.deactivate_by_id(id_)
        await session.commit()
        
    async def get_by_user(self, user_id: int) -> APIKeysRead | None:
        record = await self.repo.get_by_user(user_id)
        return APIKeysRead.model_validate(record) if record else None
