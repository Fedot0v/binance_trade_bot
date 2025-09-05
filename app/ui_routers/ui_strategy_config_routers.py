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
from strategies.base_strategy import format_params_for_display, should_show_percentage_format, PERCENTAGE_PARAMS


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
        "current_user": current_user,
        "format_params_for_display": format_params_for_display,
        "should_show_percentage_format": should_show_percentage_format,
        "percentage_params": PERCENTAGE_PARAMS
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
        "current_user": current_user,
        "format_params_for_display": format_params_for_display,
        "should_show_percentage_format": should_show_percentage_format,
        "percentage_params": PERCENTAGE_PARAMS
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
        "current_user": current_user,
        "format_params_for_display": format_params_for_display,
        "should_show_percentage_format": should_show_percentage_format,
        "percentage_params": PERCENTAGE_PARAMS
    })


@router.get("/strategy-config/{config_id}/edit/")
async def strategy_config_edit_form(
    request: Request,
    config_id: int,
    service: StrategyConfigService = Depends(get_strategy_config_service),
    current_user: User = Depends(current_active_user)
):
    config = await service.get_by_id(config_id)
    print(f"DEBUG: Загружаем стратегию {config_id} для редактирования")
    if config:
        print(f"DEBUG: Параметры стратегии: {config.parameters}")
        print(f"DEBUG: Название: {config.name}")
    else:
        print(f"DEBUG: Стратегия {config_id} не найдена")

    return templates.TemplateResponse("strategy_config/strategy_config_edit_form.html", {
        "request": request,
        "config": config,
        "format_params_for_display": format_params_for_display,
        "should_show_percentage_format": should_show_percentage_format,
        "percentage_params": PERCENTAGE_PARAMS
    })


def convert_json_params_if_novichok(params_dict: dict) -> dict:
    """
    Конвертирует процентные значения обратно в доли для Novichok стратегии.
    Если в параметрах есть ema_fast, считаем что это Novichok и конвертируем проценты.
    """
    if 'ema_fast' not in params_dict:
        return params_dict

    # Используем константу процентных параметров

    converted = params_dict.copy()
    for param in PERCENTAGE_PARAMS:
        if param in converted and isinstance(converted[param], (int, float)):
            value = converted[param]
            if value > 1:  # Если значение > 1, значит это проценты
                converted[param] = value / 100

    return converted


@router.post("/strategy-config/{config_id}/edit/")
async def strategy_config_edit(
    request: Request,
    config_id: int,
    name: str = Form(...),
    description: str = Form(""),
    is_active: str = Form("True"),
    # Параметры из JSON формы
    parameters: str = Form(None),
    # Параметры из отдельных полей формы (для Novichok)
    ema_fast: int = Form(None),
    ema_slow: int = Form(None),
    trend_threshold: float = Form(None),
    risk_pct: float = Form(None),
    deposit_prct: float = Form(None),
    stop_loss_pct: float = Form(None),
    take_profit_pct: float = Form(None),
    trailing_stop_pct: float = Form(None),
    service: StrategyConfigService = Depends(get_strategy_config_service),
    session=Depends(get_session),
    current_user: User = Depends(current_active_user)
):
    """Редактирование стратегии с поддержкой JSON и отдельных полей"""

    # Определяем, какой тип формы используется
    if ema_fast is not None:
        # Форма с отдельными полями (Novichok)
        print(f"DEBUG: Получены отдельные поля формы для Novichok")

        params_dict = {}
        if ema_fast is not None:
            params_dict['ema_fast'] = ema_fast
        if ema_slow is not None:
            params_dict['ema_slow'] = ema_slow
        if trend_threshold is not None:
            params_dict['trend_threshold'] = trend_threshold / 100  # % -> доли
        if risk_pct is not None:
            params_dict['risk_pct'] = risk_pct / 100  # % -> доли
        if deposit_prct is not None:
            params_dict['deposit_prct'] = deposit_prct / 100  # % -> доли
        if stop_loss_pct is not None:
            params_dict['stop_loss_pct'] = stop_loss_pct / 100  # % -> доли
        if take_profit_pct is not None:
            params_dict['take_profit_pct'] = take_profit_pct / 100  # % -> доли
        if trailing_stop_pct is not None:
            params_dict['trailing_stop_pct'] = trailing_stop_pct / 100  # % -> доли

        print(f"DEBUG: Сконвертированные параметры: {params_dict}")

    elif parameters:
        # JSON форма
        import json
        try:
            params_dict = json.loads(parameters)
            print(f"DEBUG: Получен JSON: {params_dict}")

            # Конвертируем проценты обратно в доли для Novichok стратегии
            params_dict = convert_json_params_if_novichok(params_dict)
            print(f"DEBUG: Параметры после конвертации: {params_dict}")
        except Exception as e:
            print(f"DEBUG: Ошибка при разборе JSON: {e}")
            # Возвращаем форму с ошибкой
            config = await service.get_by_id(config_id)
            return templates.TemplateResponse(
                "strategy_config/strategy_config_edit_form.html",
                {
                    "request": request,
                    "config": config,
                    "error": f"Ошибка в параметрах JSON: {e}"
                }
            )
    else:
        # Нет параметров
        print(f"DEBUG: Не получены параметры для обновления")
        config = await service.get_by_id(config_id)
        return templates.TemplateResponse(
            "strategy_config/strategy_config_edit_form.html",
            {
                "request": request,
                "config": config,
                "error": "Не указаны параметры стратегии"
            }
        )

    # Обновляем стратегию
    update_data = StrategyConfigUpdate(
        name=name,
        description=description,
        is_active=is_active in ("True", "true", "1"),
        parameters=params_dict
    )

    print(f"DEBUG: Обновляем стратегию {config_id} с данными: {update_data.model_dump()}")

    updated_config = await service.update_by_id(config_id, update_data, session)

    if updated_config:
        print(f"DEBUG: Стратегия успешно обновлена. Новые параметры: {updated_config.parameters}")
    else:
        print(f"DEBUG: Ошибка обновления стратегии {config_id}")

    return RedirectResponse("/strategy-config/list/", status_code=303)


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
        # Конвертируем проценты для Novichok стратегии при создании
        params = convert_json_params_if_novichok(params)
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
                 