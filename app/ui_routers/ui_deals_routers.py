from fastapi import APIRouter, Request, Depends
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
from models.user_model import User


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["Deals UI"])
current_active_user = fastapi_users.current_user(active=True)


@router.get("/deals/ui/")
async def deals_list(
    request: Request,
    service: DealService = Depends(get_deal_service),
    user: User = Depends(current_active_user)
):
    deals = await service.get_all()
    return templates.TemplateResponse("deals/deals_list.html", {
        "request": request,
        "deals": deals,
        "current_user": user
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
    log_service: APIKeysService = Depends(get_strategy_log_service)

):
    await deal_service.close_deal_manually(deal_id, session, apikeys_service)
    return RedirectResponse(f"/deals/ui/", status_code=303)
