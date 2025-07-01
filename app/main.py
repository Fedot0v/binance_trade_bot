from fastapi import FastAPI


from app.routes import user_settings_routers, user_routers, apikeys_routers, deals_routers, marketdata_routers, strategy_log_routers, strategy_config_routers, trade_router
from app.ui_routers import ui_user_routers, ui_user_settings, ui_strategy_config_routers, ui_deals_routers, ui_trade_router


app = FastAPI(
    debug=True,
    title="Novichok++ Trading API",
    description="Backend for Novichok++ bot",
    version="0.1.0"
)


app.include_router(user_settings_routers.router)
app.include_router(user_routers.router)
app.include_router(apikeys_routers.router)
app.include_router(deals_routers.router)
app.include_router(marketdata_routers.router)
app.include_router(trade_router.router)
app.include_router(strategy_log_routers.router)
app.include_router(strategy_config_routers.router)
app.include_router(ui_user_routers.router)
app.include_router(ui_user_settings.router)
app.include_router(ui_strategy_config_routers.router)
app.include_router(ui_deals_routers.router)
app.include_router(ui_trade_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
