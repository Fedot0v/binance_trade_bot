import math

from fastapi import APIRouter, Depends, Request, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from services.strategy_log_service import StrategyLogService
from dependencies.db_dependencie import get_session
from dependencies.di_factories import get_strategy_log_service
from dependencies.user_dependencies import fastapi_users


router = APIRouter(prefix="/logs", tags=["logs"])
templates = Jinja2Templates(directory="app/templates")
current_active_user = fastapi_users.current_user(active=True)


@router.get("/")
async def show_logs_by_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    log_service: StrategyLogService = Depends(get_strategy_log_service),
    current_user=Depends(current_active_user)
):
    items, total = await log_service.get_logs_by_user(
        current_user.id,
        page,
        per_page
    )
    pages = max(1, math.ceil(total / per_page))
    return templates.TemplateResponse(
        "logs/logs.html",
        {
            "request": request,
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "current_user": current_user}
    )


@router.get("/deal/{deal_id}")
async def show_logs_by_deal(
    deal_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    log_service: StrategyLogService = Depends(get_strategy_log_service),
):
    logs = await log_service.get_logs_by_deal(deal_id)
    return templates.TemplateResponse("logs/logs.html", {"request": request, "logs": logs, "deal_id": deal_id})