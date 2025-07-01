import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.services.strategy_config_service import StrategyConfigService
from app.repositories.strategy_config_repository import StrategyConfigRepository
from app.dependencies.db_dependencie import get_session
from app.dependencies.di_factories import get_service
from app.schemas.strategy_config import StrategyConfigCreate, StrategyConfigUpdate


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["StrategyConfig UI"])


get_strategy_config_service = get_service(StrategyConfigService, StrategyConfigRepository)


# Список всех стратегий
@router.get("/strategy-config/list/")
async def strategy_config_list(
    request: Request,
    service: StrategyConfigService = Depends(get_strategy_config_service)
):
    configs = await service.get_active()
    return templates.TemplateResponse("strategy_config/strategy_config_list.html", {
        "request": request,
        "configs": configs
    })


# Форма создания стратегии
@router.get("/strategy-config/create/")
async def strategy_config_create_form(request: Request):
    return templates.TemplateResponse("strategy_config/strategy_config_create_form.html", {
        "request": request
    })


# Обработка формы создания
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


# Страница просмотра стратегии
@router.get("/strategy-config/{config_id}")
async def strategy_config_detail(
    request: Request,
    config_id: int,
    service: StrategyConfigService = Depends(get_strategy_config_service)
):
    config = await service.get_by_id(config_id)
    return templates.TemplateResponse("strategy_config/strategy_config_detail.html", {
        "request": request,
        "config": config
    })


# Форма редактирования
@router.get("/strategy-config/{config_id}/edit/")
async def strategy_config_edit_form(
    request: Request,
    config_id: int,
    service: StrategyConfigService = Depends(get_strategy_config_service)
):
    config = await service.get_by_id(config_id)
    return templates.TemplateResponse("strategy_config/strategy_config_edit_form.html", {
        "request": request,
        "config": config
    })


# Обработка формы редактирования
@router.post("/strategy-config/{config_id}/edit/")
async def edit_strategy_config(
    request: Request,
    config_id: int,
    name: str = Form(...),
    description: str = Form(""),
    is_active: str = Form("True"),
    parameters: str = Form(...),
    service: StrategyConfigService = Depends(get_strategy_config_service),
    session=Depends(get_session)
):
    params = json.loads(parameters)

    data = StrategyConfigUpdate(
        name=name,
        description=description,
        is_active=is_active in ("True", "true", "1"),
        parameters=params
    )
    await service.update(config_id, data, session)
    return RedirectResponse(f"/strategy-config/list/", status_code=303)
