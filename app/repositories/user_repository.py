from sqlalchemy import select, update, delete

from app.repositories.base_repository import BaseRepository
from app.models import UserSettings


class UserSettingsRepository(BaseRepository):
    async def add(
        self,
        deposit: float,
        leverage: float,
        entry_pct: float,
        strategy_name: str
    ):
        settings = UserSettings(
            deposit=deposit,
            leverage=leverage,
            entry_pct=entry_pct,
            strategy_name=strategy_name
        )
        self.db.add(settings)
        await self.db.flush()
        await self.db.refresh(settings)
        return settings

    async def get_by_id(self, id_: int):
        result = await self.db.execute(
            select(UserSettings)
            .where(UserSettings.id == id_)
        )
        return result.scalar_one_or_none()

    async def update_by_id(self, id_: int, **kwargs):
        await self.db.execute(
            update(UserSettings)
            .where(UserSettings.id == id_)
            .values(**kwargs)
        )
        await self.db.flush()

    async def delete_by_id(self, id_: int):
        await self.db.execute(
            delete(UserSettings)
            .where(UserSettings.id == id_)
        )
        await self.db.flush()
