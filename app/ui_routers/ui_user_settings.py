from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.services.user_service_settings import UserSettingsService
from app.repositories.user_repository import UserSettingsRepository
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service
from app.schemas.user_settings import UserSettingsCreate, UserSettingsUpdate


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["UserSettings UI"])


get_user_settings_service = get_service(UserSettingsService, UserSettingsRepository)


# Список всех настроек пользователя (например, user_id=1)
@router.get("/user-settings/list/")
async def user_settings_list(
    request: Request,
    service: UserSettingsService = Depends(get_user_settings_service),
    user_id: int = 1  # Для теста, потом сделай через select или query
):
    settings = await service.get_all(user_id)
    return templates.TemplateResponse("user_settings/user_settings_list.html", {
        "request": request,
        "settings": settings,
        "user_id": user_id,
    })


# Форма создания
@router.get("/user-settings/create/")
async def user_settings_create_form(request: Request, user_id: int = 1):
    return templates.TemplateResponse("user_settings/user_settings_create_form.html", {
        "request": request, "user_id": user_id
    })


# Обработка формы создания
@router.post("/user-settings/create/")
async def create_user_settings(
    request: Request,
    deposit: float = Form(...),
    leverage: float = Form(...),
    entry_pct: float = Form(...),
    strategy_name: str = Form(...),
    user_id: int = Form(...),
    service: UserSettingsService = Depends(get_user_settings_service),
    session=Depends(get_session),
):
    data = UserSettingsCreate(
        deposit=deposit,
        leverage=leverage,
        entry_pct=entry_pct,
        strategy_name=strategy_name
    )
    await service.create(data, user_id, session)
    return RedirectResponse(f"/user-settings/list/?user_id={user_id}", status_code=303)


# Страница просмотра/редактирования
@router.get("/user-settings/{settings_id}")
async def user_settings_detail(
    request: Request,
    settings_id: int,
    service: UserSettingsService = Depends(get_user_settings_service),
    user_id: int = 1
):
    settings = await service.get_by_id(settings_id, user_id)
    return templates.TemplateResponse("user_settings/user_settings_detail.html", {
        "request": request,
        "settings": settings
    })


# Форма редактирования
@router.get("/user-settings/{settings_id}/edit/")
async def user_settings_edit_form(
    request: Request,
    settings_id: int,
    service: UserSettingsService = Depends(get_user_settings_service),
    user_id: int = 1
):
    settings = await service.get_by_id(settings_id, user_id)
    return templates.TemplateResponse("user_settings/user_settings_edit_form.html", {
        "request": request,
        "settings": settings
    })


# Обработка формы редактирования
@router.post("/user-settings/{settings_id}/edit/")
async def edit_user_settings(
    request: Request,
    settings_id: int,
    deposit: float = Form(...),
    leverage: float = Form(...),
    entry_pct: float = Form(...),
    strategy_name: str = Form(...),
    user_id: int = Form(...),
    service: UserSettingsService = Depends(get_user_settings_service),
    session=Depends(get_session)
):
    data = UserSettingsUpdate(
        deposit=deposit,
        leverage=leverage,
        entry_pct=entry_pct,
        strategy_name=strategy_name
    )
    await service.update(settings_id, data, user_id, session)
    return RedirectResponse(f"/user-settings/list/?user_id={user_id}", status_code=303)
