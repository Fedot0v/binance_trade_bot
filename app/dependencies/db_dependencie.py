from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession


from app.db.database import async_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
