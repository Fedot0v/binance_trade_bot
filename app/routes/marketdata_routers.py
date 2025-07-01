from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.marketdata_service import MarketDataService
from app.schemas.market_data import MarketDataCreate, MarketDataRead
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service
from app.repositories.marketdata_repository import MarketDataRepository


get_marketdata_service = get_service(MarketDataService, MarketDataRepository)


router = APIRouter(prefix="/market-data", tags=["Market Data"])


@router.post("/", response_model=list[MarketDataRead], status_code=status.HTTP_201_CREATED)
async def add_market_data(
    data: list[MarketDataCreate],
    service: MarketDataService = Depends(get_marketdata_service),
    session: AsyncSession = Depends(get_session)
):
    return await service.add_many(data, session)


@router.get("/latest", response_model=list[MarketDataRead])
async def get_latest_market_data(
    symbol: str,
    limit: int = 100,
    service: MarketDataService = Depends(get_marketdata_service)
):
    return await service.get_latest(symbol, limit)
