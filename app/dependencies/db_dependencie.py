from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session


# Зависимость для FastAPI
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
