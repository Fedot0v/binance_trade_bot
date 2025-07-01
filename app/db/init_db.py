import asyncio
from app.db.database import engine
from app.models.base import Base
from app.models.trade_models import (
    Deal,
    StrategyLog,
    MarketData,
    StrategyConfig
)
from app.models.user_model import User, UserSettings


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
