from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.apikeys_service import APIKeysService
from schemas.apikey import APIKeysCreate, APIKeysRead
from dependencies.db_dependencie import get_session
from dependencies.di_factories import get_service
from repositories.apikeys_repository import APIKeysRepository


get_apikeys_service = get_service(
    APIKeysService,
    APIKeysRepository
)


router = APIRouter(prefix="/apikeys", tags=["API Keys"])


@router.post(
    "/",
    response_model=APIKeysRead,
    status_code=status.HTTP_201_CREATED
)
async def create_apikey(
    data: APIKeysCreate,
    service: APIKeysService = Depends(get_apikeys_service),
    session: AsyncSession = Depends(get_session)
):
    return await service.create(data, session)

@router.get("/active", response_model=APIKeysRead)
async def get_active_apikey(
    service: APIKeysService = Depends(get_apikeys_service)
):
    result = await service.get_active()
    return result

@router.post("/deactivate/{id_}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_apikey(
    id_: int,
    service: APIKeysService = Depends(get_apikeys_service),
    session: AsyncSession = Depends(get_session)
):
    await service.deactivate(id_, session)
    return None
