import os

from fastapi import APIRouter, Request, Form, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_users.exceptions import InvalidCredentialsException
from passlib.context import CryptContext
import httpx

from auth.config import jwt_backend as auth_backend
from auth.user_manager import get_user_manager


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["auth-ui"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET = os.environ.get("AUTH_SECRET", "SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
COOKIE_NAME = "binauth"


@router.get("/login/")
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login/")
async def login_post(request: Request, response: Response):
    form = await request.form()
    email = form.get("username")
    password = form.get("password")

    user_manager = await get_user_manager()
    try:
        user = await user_manager.authenticate(credentials={"email": email, "password": password})
    except InvalidCredentialsException:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверная почта или пароль"
        })

    await auth_backend.login(response, user)
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


@router.get("/ui/register/")
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request, "error": None})


@router.post("/ui/register/")
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post(
            "/auth/register",
            json={"email": email, "password": password}
        )
    if response.status_code == 201:
        return RedirectResponse("/ui/login/", status_code=303)
    else:
        return templates.TemplateResponse(
            "auth/register.html", {"request": request, "error": "Ошибка регистрации"}
        )


@router.get("/ui/logout/")
async def logout(response: Response):
    resp = RedirectResponse(url="/ui/login/", status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp
