from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.user import UserCreate, UserRead
from dependencies.db_dependencie import get_session
from dependencies.di_factories import get_service  # если используешь фабрику
from dependencies.user_dependencies import fastapi_users
from models.user_model import User


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(superuser=True)



@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(current_active_user)):
    return user


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: str,
    user: User = Depends(current_superuser),
    user_manager=Depends(fastapi_users.get_user_manager),
):
    user_obj = await user_manager.get(user_id)
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")
    return user_obj


@router.get("/", response_model=list[UserRead])
async def get_all_users(
    user: User = Depends(current_superuser),
    user_manager=Depends(fastapi_users.get_user_manager),
):
    return await user_manager.user_db.get_all()
