from datetime import datetime

from sqlalchemy import select

from repositories.base_repository import BaseRepository
from models.bot_model import UserBot


class UserBotRepository(BaseRepository):
    async def create(self, user_id, template_id, symbol) -> UserBot:
        bot = UserBot(
            user_id=user_id,
            template_id=template_id,
            symbol=symbol,
            status="active",
            started_at=datetime.now(),
            stopped_at=None
        )
        self.db.add(bot)
        await self.db.flush()
        await self.db.refresh(bot)
        return bot

    async def stop(self, bot_id) -> None:
        result = await self.db.execute(
            select(UserBot)
            .where(UserBot.id == bot_id)
        )
        bot = result.scalar_one_or_none()
        if bot:
            bot.status = "stopped"
            bot.stopped_at = datetime.now()
            await self.db.flush()

    async def get_active_bot(self, user_id, symbol) -> UserBot | None:
        result = await self.db.execute(
            select(UserBot)
            .where(UserBot.user_id == user_id)
            .where(UserBot.symbol == symbol)
            .where(UserBot.status == "active")
        )
        return result.scalar_one_or_none()

    async def activate_bot(self, bot_id):
        result = await self.db.execute(
            select(UserBot)
            .where(UserBot.id == bot_id)
        )
        bot = result.scalar_one_or_none()
        if bot:
            bot.status = "active"
            bot.started_at = datetime.utcnow()
            bot.stopped_at = None
            await self.db.flush()
            await self.db.refresh(bot)
        return bot
    
    async def get_by_user_template_symbol(self, user_id, template_id, symbol):
        result = await self.db.execute(
            select(UserBot)
            .where(UserBot.user_id == user_id)
            .where(UserBot.template_id == template_id)
            .where(UserBot.symbol == symbol)
        )
        return result.scalar_one_or_none()
    
    async def get_by_user(self, user_id):
        result = await self.db.execute(
            select(UserBot).where(UserBot.user_id == user_id)
        )
        return result.scalars().all()

    async def get_all_active_bots(self, session):
        result = await session.execute(
            select(UserBot).where(UserBot.status == "active")
        )
        return result.scalars().all()
