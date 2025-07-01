from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from app.services.user_service_settings import UserService  # Импортируй свой сервис!
from app.schemas.user import UserCreate, UserRead
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service  # если используешь фабрику

# Создаём зависимость для UserService
get_user_service = get_service(UserService, UserRepository)

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session)
):
    user = await service.create(data.name, session)
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)

@router.get("/", response_model=list[UserRead])
async def get_all_users(
    service: UserService = Depends(get_user_service)
):
    users = await service.get_all()
    return [UserRead.model_validate(u) for u in users]
