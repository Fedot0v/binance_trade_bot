import math

from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from services.deal_service import DealService

from dependencies.db_dependencie import get_session
from dependencies.di_factories import (
    get_deal_service,
    get_apikeys_service,
    get_binance_factory,
    get_strategy_log_service
)
from dependencies.user_dependencies import fastapi_users
from services.apikeys_service import APIKeysService
from services.strategy_log_service import StrategyLogService
from models.user_model import User


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["Deals UI"])
current_active_user = fastapi_users.current_user(active=True)


@router.get("/deals/ui/")
async def deals_list(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: DealService = Depends(get_deal_service),
    user: User = Depends(current_active_user),
):
    items, total = await service.list_paginated(page=page, per_page=per_page)
    pages = max(1, math.ceil(total / per_page))
    return templates.TemplateResponse("deals/deals_list.html", {
        "request": request,
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "current_user": user,
    })


@router.get("/deals/ui/{deal_id}")
async def deal_detail(
    request: Request,
    deal_id: int,
    service: DealService = Depends(get_deal_service),
    session=Depends(get_session),
    current_user: User = Depends(current_active_user)
):
    deal = await service.get_by_id(deal_id, session)
    return templates.TemplateResponse("deals/deal_detail.html", {
        "request": request,
        "deal": deal,
        "current_user": current_user
    })


@router.post("/deals/ui/delete/{deal_id}")
async def delete_deal(
    deal_id: int,
    service: DealService = Depends(get_deal_service),
    session=Depends(get_session)
):
    await service.delete_by_id(deal_id, session)
    return RedirectResponse("/deals/ui/", status_code=303)


@router.post("/deals/{deal_id}/close")
async def close_deal(
    deal_id: int,
    session=Depends(get_session),
    deal_service: DealService = Depends(get_deal_service),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
    binance_client=Depends(get_binance_factory),
    log_service: StrategyLogService = Depends(get_strategy_log_service)

):
    await deal_service.close_deal_manually(deal_id, session, apikeys_service)
    return RedirectResponse(f"/deals/ui/", status_code=303)
