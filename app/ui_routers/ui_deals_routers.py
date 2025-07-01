from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.deal_service import DealService
from app.repositories.deal_repository import DealRepository
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["Deals UI"])
get_deal_service = get_service(DealService, DealRepository)

# Список сделок
@router.get("/deals/ui/")
async def deals_list(
    request: Request,
    service: DealService = Depends(get_deal_service)
):
    deals = await service.get_all()  # или get_open()/get_by_user(user_id) по логике
    return templates.TemplateResponse("deals/deals_list.html", {
        "request": request,
        "deals": deals
    })

# Детали сделки
@router.get("/deals/ui/{deal_id}")
async def deal_detail(
    request: Request,
    deal_id: int,
    service: DealService = Depends(get_deal_service)
):
    deal = await service.get_by_id(deal_id)
    return templates.TemplateResponse("deals/deal_detail.html", {
        "request": request,
        "deal": deal
    })
