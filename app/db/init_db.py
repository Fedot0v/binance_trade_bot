import asyncio

from db.database import engine
from models.base import Base
from models.trade_models import (
    Deal,
    StrategyLog,
    StrategyConfig,
    APIKeys
)
from models.user_model import User, UserStrategyTemplate, Intervals, Symbols
from models.bot_model import UserBot


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
