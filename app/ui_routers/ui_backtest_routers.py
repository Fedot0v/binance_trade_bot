import os

from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.backtest.backtest_service import BacktestService
from services.user_strategy_template_service import UserStrategyTemplateService
from schemas.user_strategy_template import UserStrategyTemplateRead

from dependencies.user_dependencies import fastapi_users
from dependencies.di_factories import get_user_strategy_template_service


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
backtest_service = BacktestService()
current_active_user = fastapi_users.current_user(active=True)


@router.get("/backtest/run/", response_class=HTMLResponse)
async def backtest_form(
    request: Request,
    current_user=Depends(current_active_user),
    user_strategy_template_service: UserStrategyTemplateService = Depends(
        get_user_strategy_template_service
    )
):
    templates_list = await user_strategy_template_service.get_all(
        current_user.id
    )
    return templates.TemplateResponse(
        "backtest/run.html", 
        {"request": request, "templates": templates_list, "result": None, "current_user": current_user}
    )


@router.post("/backtest/run/", response_class=HTMLResponse)
async def backtest_run(
    request: Request,
    template_id: int = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(current_active_user),
    user_strategy_template_service: UserStrategyTemplateService = Depends(
        get_user_strategy_template_service
    )
):
    templates_list = await user_strategy_template_service.get_all(
        current_user.id
    )
    selected_tpl = next(
        (tpl for tpl in templates_list if tpl.id == template_id),
        None
    )
    if not selected_tpl:
        return templates.TemplateResponse(
            "backtest/run.html", 
            {"request": request, "templates": templates_list, "result": None, "error": "Шаблон не найден"}
        )
    tmp_path = f"/tmp/{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(await file.read())
    result = await backtest_service.run_backtest(selected_tpl, tmp_path)
    os.remove(tmp_path)
    return templates.TemplateResponse(
        "backtest/run.html", 
        {"request": request, "templates": templates_list, "result": result, "current_user": current_user}
    )
