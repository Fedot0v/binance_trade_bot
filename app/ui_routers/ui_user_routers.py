from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service_settings import UserService
from app.repositories.user_repository import UserRepository
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service
from app.services.apikeys_service import APIKeysService
from app.repositories.apikeys_repository import APIKeysRepository
from app.schemas.apikey import APIKeysCreate


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["Users UI"])

get_user_service = get_service(UserService, UserRepository)
get_apikeys_service = get_service(APIKeysService, APIKeysRepository)


# Список пользователей
@router.get("/users/ui/")
async def users_list(
    request: Request,
    service: UserService = Depends(get_user_service)
):
    users = await service.get_all()
    return templates.TemplateResponse("users/user_list.html", {"request": request, "users": users})


# Форма создания пользователя
@router.get("/users/ui/create/")
async def user_create_form(request: Request):
    return templates.TemplateResponse("users/user_create_form.html", {"request": request})


# Обработка формы (создание пользователя)
@router.post("/users/ui/create/")
async def create_user(
    request: Request,
    name: str = Form(...),
    service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session)
):
    await service.create(name, session)
    return RedirectResponse("/users/ui/", status_code=303)


# Страница пользователя по id
@router.get("/users/ui/{user_id}")
async def user_detail(
    request: Request,
    user_id: int,
    service: UserService = Depends(get_user_service),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
):
    user = await service.get_by_id(user_id)
    apikey = await apikeys_service.get_by_user(user_id)  # Такой метод должен быть в сервисе/репозитории
    return templates.TemplateResponse(
        "users/user_detail.html",
        {"request": request, "user": user, "apikey": apikey}
    )


@router.get("/test")
async def test(request: Request):
    return {"msg": "UI router работает"}


@router.get("/users/ui/{user_id}/apikey/create/")
async def apikey_create_form(request: Request, user_id: int):
    return templates.TemplateResponse("apikeys/apikey_create_form.html", {
        "request": request, "user_id": user_id
    })


@router.post("/users/ui/{user_id}/apikey/create/")
async def apikey_create(
    request: Request,
    user_id: int,
    api_key: str = Form(...),
    api_secret: str = Form(...),
    service: APIKeysService = Depends(get_apikeys_service),
    session=Depends(get_session)
):
    data = APIKeysCreate(api_key=api_key, api_secret=api_secret, is_active=True, user_id=user_id)
    await service.create(data, session)
    return RedirectResponse(f"/users/ui/{user_id}", status_code=303)
