import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from celery_app import celery_app
from utils.trade_service_factory import build_trade_service
from services.deal_service import DealService
from repositories.deal_repository import DealRepository
from utils.trade_service_factory import build_deal_service


@celery_app.task
def run_active_bots():
    print("RUN_ACTIVE_BOTS LAUNCHED")
    import asyncio

    async def main():
        DATABASE_URL = os.environ.get("DATABASE_URL")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        async with async_session() as session:
            trade_service = build_trade_service(session)

            active_bots = (
                await trade_service.userbot_service.get_all_active_bots(
                    session
                )
            )
            for bot in active_bots:
                print(f"Processing bot: {bot.id}, user: {bot.user_id}, symbol: {bot.symbol}")
                periodic_trade_cycle.apply_async((
                    bot.id,
                    str(bot.user_id),
                    bot.symbol)
                )
        await engine.dispose()

    asyncio.run(main())


@celery_app.task
def periodic_trade_cycle(bot_id, user_id, symbol):
    import asyncio
    from uuid import UUID

    async def main():
        bot_id_converted = (
            int(bot_id)
            if isinstance(bot_id, str)
            else bot_id
        )
        user_id_converted = (
            UUID(user_id)
            if isinstance(user_id, str)
            else user_id
        )

        DATABASE_URL = os.environ.get("DATABASE_URL")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        async with async_session() as session:
            trade_service = build_trade_service(session)
            await trade_service.run_trading_cycle(
                bot_id=bot_id_converted,
                user_id=user_id_converted,
                symbol=symbol,
                session=session,
                test_mode=False,
            )
        await engine.dispose()

    asyncio.run(main())


@celery_app.task
def watcher_update_deals():
    import asyncio

    async def main():
        DATABASE_URL = os.environ.get("DATABASE_URL")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        async with async_session() as session:
            deal_service: DealService = build_deal_service(session)
            await deal_service.watcher_cycle(session)
    asyncio.run(main())
