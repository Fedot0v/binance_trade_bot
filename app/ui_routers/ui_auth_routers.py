import os

from fastapi import APIRouter, Request, Form, Response
from fastapi_users.password import PasswordHelper
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
import httpx
from passlib.context import CryptContext


templates = Jinja2Templates(directory="templates")
router = APIRouter(tags=["auth-ui"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password_helper = PasswordHelper()

SECRET = os.environ.get("AUTH_SECRET", "SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
COOKIE_NAME = "binauth"

templates = Jinja2Templates(directory="templates")
router = APIRouter(tags=["auth-ui"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/ui/login/")
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})

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
    resp.delete_cookie("binauth", path="/")
    return resp
