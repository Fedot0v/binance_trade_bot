from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db_dependencie import get_session
from dependencies.di_factories import get_service, get_apikeys_service
from services.apikeys_service import APIKeysService
from repositories.apikeys_repository import APIKeysRepository
from schemas.apikey import APIKeysCreate
from dependencies.user_dependencies import fastapi_users
from models.user_model import User


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["Users UI"])

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(superuser=True)


@router.get("/users/ui/me/")
async def user_profile(
    request: Request,
    current_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    apikey_service: APIKeysService = Depends(get_apikeys_service)
):
    apikeys = await apikey_service.get_by_user(current_user.id)
    return templates.TemplateResponse(
        "users/user_detail.html",
        {
            "request": request,
            "user": current_user,
            "apikeys": apikeys,
            "current_user": current_user,
        }
    )


@router.get("/users/ui/")
async def users_list(
    request: Request,
    user: User = Depends(current_active_user),
    user_manager=Depends(fastapi_users.get_user_manager),
):
    users = await user_manager.user_db.get_all()
    return templates.TemplateResponse("users/user_list.html", {"request": request, "users": users, "current_user": user})


@router.get("/users/ui/{user_id}")
async def user_detail_by_id(
    request: Request,
    user_id: str,
    current_user: User = Depends(current_superuser),
    user_manager=Depends(fastapi_users.get_user_manager),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
):
    user = await user_manager.get(user_id)
    apikeys = await apikeys_service.get_by_user(user_id)
    return templates.TemplateResponse(
        "users/user_detail.html",
        {"request": request, "user": user, "apikeys": apikeys, "current_user": current_user}
    )


@router.get("/users/ui/me/edit/")
async def edit_my_profile(
    request: Request,
    current_user: User = Depends(current_active_user),
):
    return templates.TemplateResponse("users/user_edit_form.html", {"request": request, "user": current_user})


@router.post("/users/ui/me/edit/")
async def edit_my_profile_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    current_user: User = Depends(current_active_user),
    user_manager=Depends(fastapi_users.get_user_manager),
    session: AsyncSession = Depends(get_session)
):
    user = current_user
    user.username = username
    user.email = email
    session.add(user)
    await session.commit()
    return RedirectResponse(f"/users/ui/me/", status_code=303)
