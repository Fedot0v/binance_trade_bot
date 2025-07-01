from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.services.trade_service import TradeService
from app.dependencies.di_factories import get_service  # если нужен DI
from app.dependencies.di_factories import get_trade_service


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["TradeBot UI"])


# Главная страница управления ботом (по user_id)
@router.get("/trade/ui/{user_id}")
async def trade_dashboard(
    request: Request,
    user_id: int,
    trade_service: TradeService = Depends(get_trade_service)
):
    # Можно расширить: статус бота, логи, сделки, ошибки...
    status = await trade_service.get_bot_status(user_id)
    logs = await trade_service.get_logs(user_id)
    return templates.TemplateResponse("trade/trade_dashboard.html", {
        "request": request,
        "user_id": user_id,
        "status": status,
        "logs": logs
    })

# Кнопка "Запустить бота"
@router.post("/trade/ui/{user_id}/start/")
async def trade_start(
    request: Request,
    user_id: int,
    trade_service: TradeService = Depends(get_trade_service)
):
    await trade_service.start_trading(user_id)
    return RedirectResponse(f"/trade/ui/{user_id}", status_code=303)

# Кнопка "Остановить бота"
@router.post("/trade/ui/{user_id}/stop/")
async def trade_stop(
    request: Request,
    user_id: int,
    trade_service: TradeService = Depends(get_trade_service)
):
    await trade_service.stop_trading(user_id)
    return RedirectResponse(f"/trade/ui/{user_id}", status_code=303)


@router.get("/trade/ui/hub/")
async def trade_hub(
    request: Request,
    user_id: int = 1,  # Можно сделать выбор из списка пользователей
    trade_service: TradeService = Depends(get_trade_service)
):
    status = await trade_service.get_bot_status(user_id)
    logs = await trade_service.get_logs(user_id)
    # Можно добавить актуальную сделку, активную стратегию и пр.
    return templates.TemplateResponse("trade/trade_hub.html", {
        "request": request,
        "user_id": user_id,
        "status": status,
        "logs": logs,
    })
