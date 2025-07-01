from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user_settings import (
    UserSettingsCreate,
    UserSettingsUpdate,
    UserSettingsRead,
)
from app.services.user_service_settings import UserSettingsService
from app.repositories.user_repository import UserSettingsRepository
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service

get_user_settings_service = get_service(
    UserSettingsService,
    UserSettingsRepository
)

router = APIRouter(
    prefix="/user-settings",
    tags=["User Settings"]
)

@router.post(
    "/",
    response_model=UserSettingsRead,
    status_code=status.HTTP_201_CREATED
)
async def create_user_settings(
    data: UserSettingsCreate,
    user_id: int = Query(..., description="ID пользователя"),
    service: UserSettingsService = Depends(get_user_settings_service),
    session: AsyncSession = Depends(get_session),
):
    return await service.create(data=data, user_id=user_id, session=session)

@router.get("/", response_model=List[UserSettingsRead])
async def get_user_settings(
    user_id: int = Query(..., description="ID пользователя"),
    service: UserSettingsService = Depends(get_user_settings_service),
):
    result = await service.get_all(user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User settings not found")
    return result

@router.patch("/{id_}", response_model=UserSettingsRead)
async def update_user_settings(
    id_: int,
    data: UserSettingsUpdate,
    user_id: int = Query(..., description="ID пользователя"),
    service: UserSettingsService = Depends(get_user_settings_service),
    session: AsyncSession = Depends(get_session),
):
    updated = await service.update(id_, data, user_id, session)
    if not updated:
        raise HTTPException(status_code=404, detail="User settings not found")
    return updated

@router.delete("/{id_}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_settings(
    id_: int,
    user_id: int = Query(..., description="ID пользователя"),
    service: UserSettingsService = Depends(get_user_settings_service),
    session: AsyncSession = Depends(get_session),
):
    await service.delete(id_, user_id, session)
    return None
