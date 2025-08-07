from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from dependencies.user_dependencies import fastapi_users
from models.user_model import User
from services.apikeys_service import APIKeysService
from dependencies.db_dependencie import get_session
from dependencies.di_factories import get_apikeys_service
from schemas.apikey import APIKeysCreate


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["API Keys UI"])


current_active_user = fastapi_users.current_user(active=True)


@router.get("/users/ui/me/apikey/create/")
async def apikey_create_form(
    request: Request,
    current_user: User = Depends(current_active_user),
):
    return templates.TemplateResponse("apikeys/apikey_create_form.html", {
        "request": request,
        "user_id": current_user.id
    })


@router.post("/users/ui/me/apikey/create/")
async def apikey_create_post(
    request: Request,
    api_key: str = Form(...),
    api_secret: str = Form(...),
    current_user: User = Depends(current_active_user),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
    session=Depends(get_session),
):
    data = APIKeysCreate(
        user_id=current_user.id,
        api_key=api_key,
        api_secret=api_secret,
        is_active=True
    )
    await apikeys_service.create(data, session)
    return RedirectResponse(f"/users/ui/me/", status_code=303)


@router.post("/users/ui/me/apikey/delete/{apikey_id}/")
async def delete_apikey(
    apikey_id: int,
    current_user: User = Depends(current_active_user),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
    session=Depends(get_session)
):
    await apikeys_service.delete_for_user(apikey_id, current_user.id, session)
    return RedirectResponse("/users/ui/me/", status_code=303)
