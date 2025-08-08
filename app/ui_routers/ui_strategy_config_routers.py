import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from services.strategy_config_service import StrategyConfigService
from repositories.strategy_config_repository import StrategyConfigRepository
from dependencies.db_dependencie import get_session
from dependencies.di_factories import get_service
from schemas.strategy_config import StrategyConfigCreate, StrategyConfigUpdate
from dependencies.user_dependencies import fastapi_users
from models.user_model import User, Symbols, Intervals


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["StrategyConfig UI"])

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(superuser=True)

get_strategy_config_service = get_service(
    StrategyConfigService,
    StrategyConfigRepository
)


@router.get("/strategy-config/list/")
async def strategy_config_list(
    request: Request,
    config_strategy_service: StrategyConfigService = Depends(
        get_strategy_config_service
    ),
    current_user: User = Depends(current_active_user)
):
    strategies = await config_strategy_service.get_active()
    strategy_ids = await config_strategy_service.get_all_ids()
    return templates.TemplateResponse("strategy_config/strategy_config_list.html", {
        "request": request,
        "strategies": strategies,
        "strategy_ids": strategy_ids,
        "current_user": current_user
    })


@router.get("/strategy-config/create/")
async def strategy_config_create_form(
    request: Request,
    current_user: User = Depends(current_active_user)
):
    symbols = [s.value for s in Symbols]
    intervals = [i.value for i in Intervals]
    return templates.TemplateResponse("strategy_config/strategy_config_create_form.html", {
        "request": request,
        "symbols": symbols,
        "intervals": intervals,
        "current_user": current_user
    })


@router.post("/strategy-config/create/")
async def create_strategy_config(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    is_active: str = Form("True"),
    parameters: str = Form(...),
    service: StrategyConfigService = Depends(get_strategy_config_service),
    session=Depends(get_session)
):
    params = json.loads(parameters)

    data = StrategyConfigCreate(
        name=name,
        description=description,
        is_active=is_active in ("True", "true", "1"),
        parameters=params
    )
    await service.create(data, session)
    return RedirectResponse("/strategy-config/list/", status_code=303)


@router.get("/strategy-config/{config_id}")
async def strategy_config_detail(
    request: Request,
    config_id: int,
    service: StrategyConfigService = Depends(get_strategy_config_service),
    current_user: User = Depends(current_active_user)
):
    config = await service.get_by_id(config_id)
    return templates.TemplateResponse("strategy_config/strategy_config_detail.html", {
        "request": request,
        "config": config,
        "current_user": current_user
    })


@router.get("/strategy-config/{config_id}/edit/")
async def strategy_config_edit_form(
    request: Request,
    config_id: int,
    service: StrategyConfigService = Depends(get_strategy_config_service),
    current_user: User = Depends(current_active_user)
):
    config = await service.get_by_id(config_id)
    return templates.TemplateResponse("strategy_config/strategy_config_edit_form.html", {
        "request": request,
        "config": config
    })


@router.post("/strategy-config/manual-create/")
async def strategy_config_manual_create_post(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    is_active: str = Form("false"),
    parameters: str = Form(...),
    service: StrategyConfigService = Depends(get_strategy_config_service),
    session=Depends(get_session),
):
    import json
    try:
        params = json.loads(parameters)
    except Exception as e:
        return templates.TemplateResponse(
            "strategy_templates/strategy_config_manual_create_form.html",
            {
                "request": request,
                "error": f"Ошибка в параметрах JSON: {e}"
            }
        )
    is_active_bool = is_active == "true"
    create_data = StrategyConfigCreate(
        name=name,
        description=description,
        is_active=is_active_bool,
        parameters=params
    )
    await service.create(create_data, session)
    return RedirectResponse("/strategy-config/list/", status_code=303)


@router.get("/strategy-config/manual-create/")
async def strategy_config_manual_create_form(
    request: Request,
    current_user: User = Depends(current_active_user)
    ):
    return templates.TemplateResponse(
        "strategy_templates/strategy_config_manual_create_form.html",
        {
            "request": request,
            "current_user": current_user,
        }
    )
