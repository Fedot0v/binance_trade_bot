from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.deal_service import DealService
from schemas.deal import DealCreate, DealRead
from dependencies.db_dependencie import get_session
from dependencies.di_factories import get_service
from repositories.deal_repository import DealRepository


get_deal_service = get_service(
    DealService,
    DealRepository
)


router = APIRouter(prefix="/deals", tags=["Deals"])


@router.post("/", response_model=DealRead, status_code=status.HTTP_201_CREATED)
async def create_deal(
    data: DealCreate,
    service: DealService = Depends(get_deal_service),
    session: AsyncSession = Depends(get_session)
):
    return await service.create(data, session)


@router.get("/open", response_model=list[DealRead])
async def get_open_deals(
    service: DealService = Depends(get_deal_service)
):
    return await service.get_open()


@router.post("/close/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_deal(
    deal_id: int,
    exit_price: float,
    pnl: float,
    service: DealService = Depends(get_deal_service),
    session: AsyncSession = Depends(get_session)
):
    await service.close(deal_id, exit_price, pnl, session)
    return None
