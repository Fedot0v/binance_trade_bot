from typing import Sequence

from sqlalchemy import select, update, delete


from app.repositories.base_repository import BaseRepository
from app.models.user_model import UserSettings, User


class UserSettingsRepository(BaseRepository):
    async def add(
        self,
        user_id: int,
        deposit: float,
        leverage: float,
        entry_pct: float,
        strategy_name: str
    ):
        settings = UserSettings(
            user_id=user_id,
            deposit=deposit,
            leverage=leverage,
            entry_pct=entry_pct,
            strategy_name=strategy_name
        )
        self.db.add(settings)
        await self.db.flush()
        await self.db.refresh(settings)
        return settings
    
    async def get_all(self, user_id: int) -> Sequence[UserSettings]:
        result = await self.db.execute(
            select(UserSettings)
            .where(UserSettings.user_id == user_id)
        )
        return result.scalars().all()

    async def get_by_id(self, id_: int, user_id: int):
        result = await self.db.execute(
            select(UserSettings)
            .where(
                UserSettings.id == id_,
                UserSettings.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def update_by_id(self, id_: int, user_id: int, **kwargs):
        await self.db.execute(
            update(UserSettings)
            .where(UserSettings.id == id_, UserSettings.user_id == user_id)
            .values(**kwargs)
        )
        await self.db.flush()

    async def delete_by_id(self, id_: int, user_id: int):
        await self.db.execute(
            delete(UserSettings)
            .where(UserSettings.id == id_, UserSettings.user_id == user_id)
        )
        await self.db.flush()



class UserRepository(BaseRepository):

    async def add(self, name: str):
        user = User(name=name)
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: int):
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str):
        result = await self.db.execute(
            select(User).where(User.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all(self):
        result = await self.db.execute(select(User))
        return result.scalars().all()
