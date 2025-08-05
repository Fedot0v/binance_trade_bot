from uuid import UUID
import logging

from fastapi import HTTPException

from repositories.apikeys_repository import APIKeysRepository
from schemas.apikey import APIKeysCreate, APIKeysRead
from encryption.crypto import encrypt
from encryption.crypto import decrypt


class APIKeysService:
    def __init__(self, repo: APIKeysRepository):
        self.repo = repo
        self.logger = logging.getLogger(__name__)

    async def get_active(self, user_id) -> APIKeysRead | None:
        apikeys = await self.repo.get_active(user_id)
        return [APIKeysRead.model_validate(a) for a in apikeys]

    async def deactivate(self, id_: int, user_id: UUID, session, autocommit: bool = True):
        try:
            await self.repo.deactivate_by_id(id_, user_id)
            if autocommit:
                await session.commit()
        except Exception as e:
            self.logger.error(
                f"Ошибка при деактивации API ключа с ID {id_}: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail="Ошибка при деактивации API ключа"
            )

    async def get_by_user(self, user_id: UUID) -> APIKeysRead | None:
        try:
            apikeys = await self.repo.get_by_user(user_id)
            return [APIKeysRead.model_validate(a) for a in apikeys]
        except HTTPException as e:
            self.logger.error(
                f"HTTP ошибка при получении API ключей для пользователя\
                    {user_id}: {str(e)}"
            )
            raise
        except Exception as e:
            self.logger.error(
                f"Ошибка при получении API ключей для пользователя \
                    {user_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail="Ошибка при получении API ключей для пользователя"
            )

    async def delete_for_user(
        self,
        apikey_id: int,
        user_id: UUID,
        session,
        autocommit: bool = True
    ):
        try:
            await self.repo.delete_for_user(apikey_id, user_id)
            if autocommit:
                await session.commit()
        except Exception as e:
            self.logger.error(
                f"Ошибка при удалении API ключа с ID \
                    {apikey_id} для пользователя {user_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail="Ошибка при удалении API ключа"
            )
        
    async def create(
        self,
        data: APIKeysCreate,
        session,
        autocommit: bool = True
    ) -> APIKeysRead:
        try:
            encrypted_secret = encrypt(data.api_secret)
            result = await self.repo.add(
                data.user_id,
                data.api_key,
                encrypted_secret,
                data.is_active if hasattr(data, 'is_active') else True
            )
            if autocommit:
                await session.commit()
            return APIKeysRead.model_validate(result)
        except Exception as e:
            self.logger.error(f"Ошибка при создании API ключа: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при создании API ключа"
            )
        
    async def get_decrypted_by_user(self, user_id: UUID):
        apikeys = await self.get_by_user(user_id)
        for key in apikeys:
            key.api_secret_encrypted = decrypt(key.api_secret_encrypted)
        return apikeys
