from app.repositories.user_repository import UserSettingsRepository
from app.schemas.user_settings import (
    UserSettingsCreate,
    UserSettingsUpdate,
    UserSettingsRead
)


class UserSettingsService:
    def __init__(self, repo: UserSettingsRepository):
        self.repo = repo

    async def create(
        self,
        data: UserSettingsCreate, session
    ) -> UserSettingsRead:
        result = await self.repo.add(**data.model_dump())
        await session.commit()
        return UserSettingsRead.model_validate(result)

    async def get_by_id(self, id_: int) -> UserSettingsRead | None:
        result = await self.repo.get_by_id(id_)
        return UserSettingsRead.model_validate(result) if result else None

    async def update(
        self,
        id_: int,
        data: UserSettingsUpdate,
        session
    ) -> UserSettingsRead | None:
        await self.repo.update_by_id(id_, **data.model_dump(exclude_none=True))
        await session.commit()
        updated = await self.repo.get_by_id(id_)
        return UserSettingsRead.model_validate(updated) if updated else None

    async def delete(self, id_: int, session):
        await self.repo.delete_by_id(id_)
        await session.commit()
