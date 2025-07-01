from app.repositories.user_repository import UserSettingsRepository, UserRepository
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
        data: UserSettingsCreate,
        user_id: int,
        session
    ) -> UserSettingsRead:
        result = await self.repo.add(
            user_id=user_id,
            **data.model_dump()
        )
        await session.commit()
        return UserSettingsRead.model_validate(result)

    async def get_by_id(self, id_: int, user_id: int) -> UserSettingsRead | None:
        result = await self.repo.get_by_id(id_, user_id)
        return UserSettingsRead.model_validate(result) if result else None

    async def get_all(self, user_id: int) -> list[UserSettingsRead]:
        results = await self.repo.get_all(user_id)
        return [UserSettingsRead.model_validate(item) for item in results]

    async def update(
        self,
        id_: int,
        data: UserSettingsUpdate,
        user_id: int,
        session
    ) -> UserSettingsRead | None:
        await self.repo.update_by_id(id_, user_id=user_id, **data.model_dump(exclude_none=True))
        await session.commit()
        updated = await self.repo.get_by_id(id_, user_id)
        return UserSettingsRead.model_validate(updated) if updated else None

    async def delete(self, id_: int, user_id: int, session):
        await self.repo.delete_by_id(id_, user_id)
        await session.commit()


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def create(self, name: str, session):
        user = await self.repo.add(name)
        await session.commit()
        return user

    async def get_by_id(self, user_id: int):
        return await self.repo.get_by_id(user_id)

    async def get_all(self):
        return await self.repo.get_all()
