from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.apikeys_service import APIKeysService
from schemas.apikey import APIKeysCreate, APIKeysRead
from dependencies.db_dependencie import get_session
from dependencies.di_factories import get_service
from repositories.apikeys_repository import APIKeysRepository
from dependencies.user_dependencies import fastapi_users
from models.user_model import User


get_apikeys_service = get_service(
    APIKeysService,
    APIKeysRepository
)

current_active_user = fastapi_users.current_user(active=True)

router = APIRouter(prefix="/apikeys", tags=["API Keys"])


@router.post(
    "/",
    response_model=APIKeysRead,
    status_code=status.HTTP_201_CREATED
)
async def create_apikey(
    data: APIKeysCreate,
    current_user: User = Depends(current_active_user),
    service: APIKeysService = Depends(get_apikeys_service),
    session: AsyncSession = Depends(get_session)
):
    # Устанавливаем user_id из текущего пользователя
    data.user_id = current_user.id
    return await service.create(data, session)

@router.get("/active", response_model=list[APIKeysRead])
async def get_active_apikey(
    current_user: User = Depends(current_active_user),
    service: APIKeysService = Depends(get_apikeys_service)
):
    result = await service.get_active(current_user.id)
    return result

@router.post("/deactivate/{id_}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_apikey(
    id_: int,
    current_user: User = Depends(current_active_user),
    service: APIKeysService = Depends(get_apikeys_service),
    session: AsyncSession = Depends(get_session)
):
    await service.deactivate(id_, current_user.id, session)
    return None
