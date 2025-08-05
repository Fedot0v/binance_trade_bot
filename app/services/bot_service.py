from repositories.bot_repository import UserBotRepository


class UserBotService:
    def __init__(self, repo: UserBotRepository):
        self.repo = repo

    async def start_bot(
        self,
        db,
        user_id,
        template_id,
        symbol,
        autocommit: bool = True
    ):
        bot = await self.repo.get_by_user_template_symbol(
            user_id,
            template_id,
            symbol
        )
        if bot:
            if bot.status != "active":
                await self.repo.activate_bot(bot.id)
                if autocommit:
                    await db.commit()
            return bot
        else:
            bot = await self.repo.create(user_id, template_id, symbol)
            if autocommit:
                await db.commit()
            return bot

    async def get_bot_by_user(self, session, user_id):
        bots = await self.repo.get_by_user(session, user_id)
        return bots

    async def stop_bot(self, bot_id, session, autocommit: bool = True):
        await self.repo.stop(bot_id)
        if autocommit:
            await session.commit()

    async def is_active(self, user_id, symbol) -> bool:
        bot = await self.repo.get_active_bot(user_id, symbol)
        return bot is not None

    async def start_existing_bot(
        self,
        session,
        bot_id,
        autocommit: bool = True
    ):
        bot = await self.repo.activate_bot(session, bot_id)
        if autocommit:
            await session.commit()
        return bot

    async def get_active_bot(self, user_id, symbol):
        bot = await self.repo.get_active_bot(user_id, symbol)
        return bot if bot else None

    async def get_all_active_bots(self, session):
        bots = await self.repo.get_all_active_bots(session)
        return bots if bots else []
