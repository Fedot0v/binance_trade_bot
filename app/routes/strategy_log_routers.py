from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.strategy_log_service import StrategyLogService
from app.schemas.strategy_log import StrategyLogCreate, StrategyLogRead
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service
from app.repositories.strategy_repository import StrategyLogRepository


get_strategy_log_service = get_service(StrategyLogService, StrategyLogRepository)


router = APIRouter(prefix="/strategy-log", tags=["Strategy Log"])

@router.post("/", response_model=StrategyLogRead, status_code=status.HTTP_201_CREATED)
async def add_strategy_log(
    data: StrategyLogCreate,
    service: StrategyLogService = Depends(get_strategy_log_service),
    session: AsyncSession = Depends(get_session)
):
    return await service.add(data, session)

@router.get("/by-deal/{deal_id}", response_model=list[StrategyLogRead])
async def get_logs_by_deal(
    deal_id: int,
    service: StrategyLogService = Depends(get_strategy_log_service)
):
    return await service.get_by_deal(deal_id)