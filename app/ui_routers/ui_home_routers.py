from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates

from dependencies.user_dependencies import fastapi_users


templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


current_active_user = fastapi_users.current_user(optional=True)


@router.get("/")
async def home(request: Request, current_user=Depends(current_active_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })
