from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.strategy_config_service import StrategyConfigService
from app.schemas.strategy_config import StrategyConfigCreate, StrategyConfigUpdate, StrategyConfigRead
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service
from app.repositories.strategy_config_repository import StrategyConfigRepository


get_strategy_config_service = get_service(
    StrategyConfigService,
    StrategyConfigRepository
)


router = APIRouter(prefix="/strategy-config", tags=["Strategy Config"])


@router.post("/", response_model=StrategyConfigRead, status_code=status.HTTP_201_CREATED)
async def create_strategy_config(
    data: StrategyConfigCreate,
    service: StrategyConfigService = Depends(get_strategy_config_service),
    session: AsyncSession = Depends(get_session)
):
    return await service.create(data, session)

@router.get("/{config_id}", response_model=StrategyConfigRead)
async def get_strategy_config(
    config_id: int,
    service: StrategyConfigService = Depends(get_strategy_config_service)
):
    result = await service.get_by_id(config_id)
    if not result:
        raise HTTPException(status_code=404, detail="Config not found")
    return result

@router.get("/", response_model=list[StrategyConfigRead])
async def get_active_configs(
    service: StrategyConfigService = Depends(get_strategy_config_service)
):
    return await service.get_active()

@router.patch("/{config_id}", response_model=StrategyConfigRead)
async def update_strategy_config(
    config_id: int,
    data: StrategyConfigUpdate,
    service: StrategyConfigService = Depends(get_strategy_config_service),
    session: AsyncSession = Depends(get_session)
):
    return await service.update(config_id, data, session)
