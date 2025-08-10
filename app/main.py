import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager


from dependencies.db_dependencie import get_session
from repositories.strategy_config_repository import StrategyConfigRepository
from services.strategy_config_service import StrategyConfigService
from routes import (
    apikeys_routers,
    deals_routers,
    strategy_log_routers,
    strategy_config_routers,
    trade_router,
    auth_routers
)
from ui_routers import (
    ui_strategy_templates,
    ui_user_routers,
    ui_strategy_config_routers,
    ui_deals_routers,
    ui_trade_router,
    ui_auth_routers,
    ui_home_routers,
    ui_apikey_routers,
    ui_strategy_log,
    ui_backtest_routers
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async for session in get_session():
        try:
            service = StrategyConfigService(StrategyConfigRepository(session))
            await service.seed_from_registry_if_missing(session)
        finally:
            await session.close()
        break
    yield


app = FastAPI(
    debug=True,
    title="Novichok++ Trading API",
    description="Backend for Novichok++ bot",
    version="0.1.0",
    lifespan=lifespan
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# app.include_router(user_settings_routers.router)
app.include_router(apikeys_routers.router)
app.include_router(deals_routers.router)
app.include_router(trade_router.router)
app.include_router(strategy_log_routers.router)
app.include_router(strategy_config_routers.router)
app.include_router(ui_user_routers.router)
app.include_router(ui_strategy_templates.router)
app.include_router(ui_strategy_config_routers.router)
app.include_router(ui_deals_routers.router)
app.include_router(ui_trade_router.router)
app.include_router(auth_routers.router)
app.include_router(ui_auth_routers.router)
app.include_router(ui_home_routers.router)
app.include_router(ui_apikey_routers.router)
app.include_router(ui_strategy_log.router)
app.include_router(ui_backtest_routers.router)


@app.get("/health")
def health():
    return {"status": "ok"}
