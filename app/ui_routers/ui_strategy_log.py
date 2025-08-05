from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from services.strategy_log_service import StrategyLogService
from dependencies.db_dependencie import get_session  # твой Depends
from dependencies.di_factories import get_strategy_log_service  # функция для DI
from dependencies.user_dependencies import fastapi_users


router = APIRouter(prefix="/logs", tags=["logs"])
templates = Jinja2Templates(directory="templates")
current_active_user = fastapi_users.current_user(active=True)


@router.get("/")
async def show_last_logs(
    request: Request,
    session: AsyncSession = Depends(get_session),
    log_service: StrategyLogService = Depends(get_strategy_log_service),
    current_user=Depends(current_active_user)
):
    logs = await log_service.get_last_logs(50)
    return templates.TemplateResponse("logs/logs.html", {"request": request, "logs": logs, "deal_id": None, "current_user": current_user})


@router.get("/deal/{deal_id}")
async def show_logs_by_deal(
    deal_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    log_service: StrategyLogService = Depends(get_strategy_log_service),
):
    logs = await log_service.get_logs_by_deal(deal_id)
    return templates.TemplateResponse("logs/logs.html", {"request": request, "logs": logs, "deal_id": deal_id})