from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from binance.client import Client

from services.user_strategy_template_service import UserStrategyTemplateService
from repositories.user_repository import UserStrategyTemplateRepository
from dependencies.db_dependencie import get_session
from models.user_model import UserStrategyTemplate
from dependencies.di_factories import get_service, get_user_strategy_template_service, get_strategy_service, get_balance_service, get_apikeys_service
from schemas.user_strategy_template import UserStrategyTemplateCreate, UserStrategyTemplateUpdate
from services.balance_service import BalanceService
from services.apikeys_service import APIKeysService

from dependencies.user_dependencies import fastapi_users
from models.user_model import User, Symbols, Intervals
from services.strategy_config_service import StrategyConfigService
from encryption.crypto import decrypt
from strategies.base_strategy import format_params_for_display, should_show_percentage_format, PERCENTAGE_PARAMS
from strategies.registry import REGISTRY


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["UserStrategyTemplates UI"])

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(superuser=True)

get_strategy_template_service = get_user_strategy_template_service

# Подсказки для параметров стратегий (краткие описания)
PARAM_HINTS = {
    # Общие/Новичок
    "ema_fast": "Быстрая EMA: меньше — чувствительнее к изменениям",
    "ema_slow": "Медленная EMA: больше — более сглаженный тренд",
    "trend_threshold": "Минимальное расхождение EMA для сигнала (доля, 0.001 = 0.1%)",
    "deposit_prct": "Доля депозита на сделку (0.1 = 10%)",
    "stop_loss_pct": "Стоп-лосс от цены входа (доля)",
    "take_profit_pct": "Тейк-профит от цены входа (доля)",
    "trailing_stop_pct": "Трейлинг-стоп (доля) — подтягивается по прибыли",
    # Компенсация
    "btc_deposit_prct": "Доля депозита на сделку BTC",
    "btc_stop_loss_pct": "Стоп-лосс BTC (доля)",
    "btc_take_profit_pct": "Тейк-профит BTC (доля)",
    "eth_deposit_prct": "Доля депозита на сделку ETH",
    "eth_stop_loss_pct": "Стоп-лосс ETH (доля)",
    "eth_take_profit_pct": "Тейк-профит ETH (доля)",
    "compensation_threshold": "Просадка BTC от входа для запуска компенсации (доля)",
    "compensation_delay_candles": "Задержка (в свечах) после первого сигнала",
    "impulse_threshold": "Импульс на свече (доля) как доп. триггер",
    "candles_against_threshold": "Мин. кол-во свечей против позиции BTC",
    "eth_confirmation_candles": "Сколько последних свечей ETH подтверждают направление",
    "require_eth_ema_alignment": "Требовать совпадения тренда ETH по EMA с ожиданием",
    "eth_volume_min_ratio": "Мин. отношение объёмов ETH (0 — отключено)",
    "high_adverse_threshold": "Сильная просадка BTC для аварийного входа (без задержки)",
    "max_compensation_window_candles": "Макс. окно ожидания компенсации от первого сигнала",
    "eth_compensation_opposite": "Если включено — ETH открывается в противоположную сторону к BTC (хедж). Если выключено — ETH открывается в ту же сторону, что и BTC.",
}

@router.get("/strategy-templates/list/")
async def strategy_template_list(
    request: Request,
    service: UserStrategyTemplateService = Depends(get_strategy_template_service),
    user: User = Depends(current_active_user),
):
    templates_ = await service.get_all(user.id)
    return templates.TemplateResponse("strategy_templates/strategy_template_list.html", {
        "request": request,
        "templates": templates_,
        "current_user": user.id,
        "format_params_for_display": format_params_for_display,
        "should_show_percentage_format": should_show_percentage_format,
        "percentage_params": PERCENTAGE_PARAMS
    })

# Форма создания
@router.get("/strategy-templates/create/")
async def strategy_template_create_form(
    request: Request,
    user: User = Depends(current_active_user),
    config_strategy_service: StrategyConfigService = Depends(get_strategy_service),
    session=Depends(get_session),
    strategy_config_id: int = Query(None)
):
    strategies = await config_strategy_service.get_active()
    selected_parameters = None
    selected_strategy_name = None
    symbols = [s.value for s in Symbols]
    intervals = [i.value for i in Intervals]
    if strategy_config_id:
        selected_parameters = await config_strategy_service.get_parameters(strategy_config_id)
        cfg = await config_strategy_service.get_by_id(strategy_config_id)
        selected_strategy_name = getattr(cfg, 'name', None)
        # Если выбран compensation — добавим отсутствующие параметры по умолчанию
        try:
            if selected_strategy_name and selected_strategy_name in REGISTRY:
                defaults = REGISTRY[selected_strategy_name]["default_parameters"]
                if not selected_parameters:
                    selected_parameters = {}
                for k, v in defaults.items():
                    if k not in selected_parameters:
                        selected_parameters[k] = v
        except Exception:
            pass
        # Параметры передаются как есть (в долях), проценты показываются динамически в шаблоне

    return templates.TemplateResponse("strategy_templates/strategy_template_create_form.html", {
        "request": request,
        "current_user": user,
        "strategies": strategies,
        "strategy_config_id": strategy_config_id,
        "parameters": selected_parameters,
        "selected_strategy_name": selected_strategy_name,
        "symbols": symbols,
        "intervals": intervals,
        "format_params_for_display": format_params_for_display,
        "should_show_percentage_format": should_show_percentage_format,
        "percentage_params": PERCENTAGE_PARAMS,
        "param_hints": PARAM_HINTS,
    })

# Обработка формы создания
@router.post("/strategy-templates/create/")
async def create_strategy_template(
    request: Request,
    template_name: str = Form(...),
    description: str = Form(None),
    initial_balance: float = Form(None),
    leverage: float = Form(...),
    symbol: str = Form(...),
    interval: str = Form(...),
    strategy_config_id: str = Form(""),  # Принимаем как строку, чтобы обработать "None"
    parameters: str = Form(None),  # Передавать JSON-строку если нужно
    service: UserStrategyTemplateService = Depends(get_strategy_template_service),
    session=Depends(get_session),
    user: User = Depends(current_active_user),
):
    form = await request.form()
    params = {k[6:]: v for k, v in form.items() if k.startswith('param_')}
    # Обрабатываем чекбокс eth_compensation_opposite (если чекбокс не отмечен — ключа не будет в форме)
    if 'eth_compensation_opposite' in params:
        params['eth_compensation_opposite'] = True if params['eth_compensation_opposite'] in ['true', 'on', '1'] else False

    # Обрабатываем strategy_config_id
    if strategy_config_id == "" or strategy_config_id == "None" or strategy_config_id is None:
        strategy_config_id_int = None
    else:
        try:
            strategy_config_id_int = int(strategy_config_id)
        except (ValueError, TypeError):
            strategy_config_id_int = None

    # Конвертируем проценты обратно в доли при создании шаблона
    if params and any(k in params for k in ['ema_fast', 'ema_slow']):
        print(f"DEBUG: Создание шаблона с параметрами: {params}")
        percentage_params = PERCENTAGE_PARAMS

        for param in percentage_params:
            if param in params and isinstance(params[param], (int, float, str)):
                try:
                    value = float(params[param])
                    if value > 1:  # Если значение > 1, значит это проценты
                        params[param] = value / 100  # Конвертируем в доли
                except (ValueError, TypeError):
                    pass  # Оставляем как есть, если не число

        print(f"DEBUG: Параметры после конвертации: {params}")

    if params:
        # Явно приводим булев параметр при создании
        if 'eth_compensation_opposite' in params and isinstance(params['eth_compensation_opposite'], str):
            params['eth_compensation_opposite'] = params['eth_compensation_opposite'].lower() in ['true', '1', 'on', 'yes']
    else:
        params = None

    symbol_enum = Symbols(symbol)
    interval_enum = Intervals(interval)
    data = UserStrategyTemplateCreate(
        template_name=template_name,
        description=description,
        initial_balance=initial_balance,
        leverage=leverage,
        symbol=symbol_enum,
        interval=interval_enum,
        strategy_config_id=strategy_config_id_int,
        parameters=params
    )
    await service.create(data, user.id, session)
    return RedirectResponse(f"/strategy-templates/list/", status_code=303)

# Страница просмотра/редактирования
@router.get("/strategy-templates/{template_id}")
async def strategy_template_detail(
    request: Request,
    template_id: int,
    service: UserStrategyTemplateService = Depends(get_strategy_template_service),
    user: User = Depends(current_active_user),
):
    template = await service.get_by_id(template_id, user.id)
    return templates.TemplateResponse("strategy_templates/strategy_template_detail.html", {
        "request": request,
        "template": template,
        "current_user": user,
        "format_params_for_display": format_params_for_display,
        "should_show_percentage_format": should_show_percentage_format,
        "percentage_params": PERCENTAGE_PARAMS
    })

# Форма редактирования
@router.get("/strategy-templates/{template_id}/edit/")
async def strategy_template_edit_form(
    request: Request,
    template_id: int,
    service: UserStrategyTemplateService = Depends(get_strategy_template_service),
    config_strategy_service: StrategyConfigService = Depends(get_strategy_service),
    user: User = Depends(current_active_user)
):
    symbols = [s.value for s in Symbols]
    intervals = [i.value for i in Intervals]

    # Получаем шаблон
    template = await service.get_by_id(template_id, user.id)

    # Используем параметры шаблона
    selected_parameters = template.parameters.copy() if template and template.parameters else None
    # Подмешаем дефолты из реестра, чтобы отрендерить недостающие ключи (например, новый чекбокс)
    try:
        cfg = await config_strategy_service.get_by_id(template.strategy_config_id)
        strategy_name = getattr(cfg, 'name', None)
        if strategy_name and strategy_name in REGISTRY:
            defaults = REGISTRY[strategy_name]["default_parameters"]
            if not selected_parameters:
                selected_parameters = {}
            for k, v in defaults.items():
                if k not in selected_parameters:
                    selected_parameters[k] = v
    except Exception:
        pass

    return templates.TemplateResponse("strategy_templates/strategy_template_edit_form.html", {
        "request": request,
        "current_user": user,
        "parameters": selected_parameters,
        "symbols": symbols,
        "intervals": intervals,
        "template": template,
        "format_params_for_display": format_params_for_display,
        "should_show_percentage_format": should_show_percentage_format,
        "percentage_params": PERCENTAGE_PARAMS,
        "param_hints": PARAM_HINTS,
    })

# Обработка формы редактирования
@router.post("/strategy-templates/{template_id}/edit/")
async def edit_strategy_template(
    request: Request,
    template_id: int,
    template_name: str = Form(...),
    description: str = Form(None),
    initial_balance: float = Form(None),
    leverage: float = Form(...),
    symbol: str = Form(...),
    interval: str = Form(...),
    parameters: str = Form(None),
    service: UserStrategyTemplateService = Depends(get_strategy_template_service),
    session=Depends(get_session),
    user: User = Depends(current_active_user),
):
    form = await request.form()
    params = {k[6:]: v for k, v in form.items() if k.startswith('param_')}
    # Обрабатываем чекбокс eth_compensation_opposite (если чекбокс не отмечен — ключа не будет в форме)
    if 'eth_compensation_opposite' in params:
        params['eth_compensation_opposite'] = True if params['eth_compensation_opposite'] in ['true', 'on', '1'] else False

    # Получаем текущий шаблон, чтобы взять strategy_config_id из него
    current_template = await service.get_by_id(template_id, user.id)

    # Конвертируем проценты обратно в доли при сохранении
    if params and any(k in params for k in ['ema_fast', 'ema_slow']):
        print(f"DEBUG: Получены параметры для сохранения: {params}")
        percentage_params = PERCENTAGE_PARAMS

        for param in percentage_params:
            if param in params and isinstance(params[param], (int, float, str)):
                try:
                    value = float(params[param])
                    if value > 1:  # Если значение > 1, значит это проценты
                        params[param] = value / 100  # Конвертируем в доли
                except (ValueError, TypeError):
                    pass  # Оставляем как есть, если не число

        print(f"DEBUG: Параметры после конвертации: {params}")

    if params:
        # Явно приводим булев параметр при обновлении
        if 'eth_compensation_opposite' in params and isinstance(params['eth_compensation_opposite'], str):
            params['eth_compensation_opposite'] = params['eth_compensation_opposite'].lower() in ['true', '1', 'on', 'yes']
    else:
        params = None

    symbol_enum = Symbols(symbol)
    interval_enum = Intervals(interval)
    data = UserStrategyTemplateCreate(
        template_name=template_name,
        description=description,
        initial_balance=initial_balance,
        leverage=leverage,
        symbol=symbol_enum,
        interval=interval_enum,
        strategy_config_id=current_template.strategy_config_id,  # Берем из текущего шаблона
        parameters=params
    )
    await service.update(template_id, data, user.id, session)
    return RedirectResponse(f"/strategy-templates/list/", status_code=303)


@router.post("/strategy-templates/fix-initial-balance/{template_id}/")
async def fix_initial_balance(
    template_id: int,
    user: User = Depends(current_active_user),
    service: UserStrategyTemplateService = Depends(get_user_strategy_template_service),
    balance_service: BalanceService = Depends(get_balance_service),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
    session=Depends(get_session),
):
    # Получить шаблон
    orm_template = await session.get(UserStrategyTemplate, template_id)
    # if not template or template.user_id != user.id:
    #     raise HTTPException(status_code=403, detail="Нет доступа к шаблону")

    # Получить ключи и баланс
    apikeys = await apikeys_service.get_active(user.id)
    if not apikeys:
        raise HTTPException(status_code=400, detail="Нет активного API-ключа")
    apikey = apikeys[0]
    decrypted_secret = decrypt(apikey.api_secret_encrypted)
    print(f"Decrypted secret: {decrypted_secret}")  # Для отладки, убери в продакшене
    print(f"API Key: {apikey.api_key_encrypted}")
    balance = await balance_service.get_futures_balance(apikey.api_key_encrypted, decrypted_secret)

    orm_template.initial_balance = balance['available']
    session.add(orm_template)
    await session.commit()
    return RedirectResponse("/trade/ui/hub/", status_code=303)



# @router.post("/strategy-templates/fix-initial-balance/{template_id}/")
# async def fix_initial_balance(
#     template_id: int,
#     user: User = Depends(current_active_user),
#     service: UserStrategyTemplateService = Depends(get_user_strategy_template_service),
#     apikeys_service: APIKeysService = Depends(get_apikeys_service),
#     session=Depends(get_session),
# ):
#     # Получить ORM-шаблон напрямую из БД!
#     orm_template = await session.get(UserStrategyTemplate, template_id) # <--- ключевой момент!

#     if not orm_template or orm_template.user_id != user.id:
#         raise HTTPException(status_code=403, detail="Нет доступа к шаблону")

#     # Получить ключи
#     apikeys = await apikeys_service.get_active(user.id)
#     if not apikeys:
#         raise HTTPException(status_code=400, detail="Нет активного API-ключа")
#     apikey = apikeys[0]
#     decrypted_secret = decrypt(apikey.api_secret_encrypted)

#     # Получить спотовый USDT-баланс
#     client = Client(apikey.api_key_encrypted, decrypted_secret)
#     try:
#         spot_balance = client.get_account()
#         usdt = next((b for b in spot_balance['balances'] if b['asset'] == 'USDT'), None)
#         usdt_free = float(usdt['free']) if usdt else 0.0
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Ошибка получения спотового баланса: {str(e)}")

#     orm_template.initial_balance = usdt_free
#     session.add(orm_template)
#     await session.commit()
#     return RedirectResponse("/trade/ui/hub/", status_code=303)
