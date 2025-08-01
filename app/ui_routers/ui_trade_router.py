from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from dependencies.user_dependencies import fastapi_users
from models.user_model import User
from dependencies.di_factories import (
    get_trade_service,
    get_deal_service,
    get_strategy_log_service,
    get_user_strategy_template_service,
    get_strategy_service,
    get_apikeys_service,
    get_balance_service,
    get_order_service,
    get_userbot_service
)
from dependencies.db_dependencie import get_session
from services.trade_service import TradeService
from services.deal_service import DealService
from services.strategy_log_service import StrategyLogService
from services.user_strategy_template_service import UserStrategyTemplateService
from services.strategy_config_service import StrategyConfigService
from services.balance_service import BalanceService
from services.order_service import OrderService
from services.apikeys_service import APIKeysService
from encryption.crypto import decrypt
from tasks.trade_tasks import periodic_trade_cycle
from services.bot_service import UserBotService


templates = Jinja2Templates(directory="templates")
router = APIRouter(tags=["Trade Hub UI"])
current_active_user = fastapi_users.current_user(active=True)

@router.get("/trade/ui/hub/")
async def trade_hub(
    request: Request,
    current_user: User = Depends(current_active_user),
    trade_service: TradeService = Depends(get_trade_service),
    user_strategy_template_service: UserStrategyTemplateService = Depends(get_user_strategy_template_service),
    balance_service: BalanceService = Depends(get_balance_service),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
    deal_service: DealService = Depends(get_deal_service),
    strategy_service: StrategyConfigService = Depends(get_strategy_service),
    bot_service: UserBotService = Depends(get_userbot_service),
    session=Depends(get_session),
):
    # Получаем всё, что нужно для шаблона
    
    all_templates = await user_strategy_template_service.get_all(current_user.id)
    active_template = await user_strategy_template_service.get_active_strategie(current_user.id)
    strategy_config = None
    if active_template:
        strategy_config = await strategy_service.get_by_id(active_template.strategy_config_id)

    # Получаем только один раз активный ключ и сразу его используем
    apikeys = await apikeys_service.get_active(current_user.id)
    apikey = apikeys[0] if apikeys else None

    balance = None
    user_balance = None
    if apikey:
        api_key = apikey.api_key_encrypted   # если ключ не шифруется, бери apikey.api_key
        api_secret = decrypt(apikey.api_secret_encrypted)
        try:
            balance_data = await balance_service.get_futures_balance(api_key, api_secret)
            balance = balance_data  # ожидается dict с 'available'
            user_balance = balance.get('available', None)
        except Exception:
            balance = None
            user_balance = None

    # last_deal = await deal_service.get_last_deal(current_user.id) if deal_service else None
    status = await trade_service.get_bot_status(current_user.id)
    # logs = await trade_service.get_logs(last_deal.id) if last_deal else []

    # Всё что ниже — только расчёты на сервере!
    template_profit = None
    template_profit_pct = None
    if active_template and active_template.initial_balance and balance:
        profit = balance.get('available', 0) - active_template.initial_balance
        profit_pct = 100 * profit / active_template.initial_balance if active_template.initial_balance else 0
        template_profit = round(profit, 2)
        template_profit_pct = round(profit_pct, 2)

    templates_data = []
    for tpl in all_templates:
        strategy_config = await strategy_service.get_by_id(tpl.strategy_config_id)
        profit = profit_pct = None
        if tpl.initial_balance and balance:
            profit = round(balance.get('available', 0) - tpl.initial_balance, 2)
            profit_pct = round(100 * profit / tpl.initial_balance, 2) if tpl.initial_balance else None
        templates_data.append({
            "tpl": tpl,
            "strategy_config": strategy_config,
            "profit": profit,
            "profit_pct": profit_pct
        })
        
    active_bot = await bot_service.get_active_bot(user_id=current_user.id, symbol="BTCUSDT")

    return templates.TemplateResponse("trade/trade_hub.html", {
        "request": request,
        "current_user": current_user,
        "status": status,
        "active_template": active_template,
        "all_templates": all_templates,
        "strategy_config": strategy_config,
        # "logs": logs,
        "balance": balance,
        # "last_deal": last_deal,
        "apikey": apikey,
        "user_balance": user_balance,
        "template_profit": template_profit,
        "template_profit_pct": template_profit_pct,
        "all_templates_data": templates_data,
        "active_bot": active_bot
    })

@router.post("/trade/ui/start/")
async def trade_start(
    request: Request,
    current_user: User = Depends(current_active_user),
    trade_service: TradeService = Depends(get_trade_service),
    user_strategy_template_service: UserStrategyTemplateService = Depends(get_user_strategy_template_service),
    bot_service: UserBotService = Depends(get_userbot_service),
    session=Depends(get_session),
):
    active_template = await user_strategy_template_service.get_active_strategie(current_user.id)
    symbol = active_template.symbol.value if active_template else "BTCUSDT"
    bot = await bot_service.start_bot(session, current_user.id, active_template.id, symbol)
    periodic_trade_cycle.apply_async(args=(bot.id, current_user.id, symbol))
    return RedirectResponse(f"/trade/ui/hub/", status_code=303)


@router.post("/trade/ui/stop/")
async def trade_stop(
    request: Request,
    current_user: User = Depends(current_active_user),
    trade_service: TradeService = Depends(get_trade_service),
    user_strategy_template_service: UserStrategyTemplateService = Depends(get_user_strategy_template_service),
    session=Depends(get_session),
):
    await trade_service.stop_trading(current_user.id, session)
    return RedirectResponse(f"/trade/ui/hub/", status_code=303)


@router.post("/strategy-templates/set-active/{template_id}/")
async def set_active_template(
    request: Request,   # это важно!
    template_id: int,
    user: User = Depends(current_active_user),
    service: UserStrategyTemplateService = Depends(get_user_strategy_template_service),
    session=Depends(get_session),
):
    await service.set_active(user.id, template_id, session)
    # Можешь явно указать путь, если не используешь url_for:
    return RedirectResponse("/trade/ui/hub/", status_code=303)


@router.post("/trade/ui/refresh-balance/")
async def refresh_balance(
    request: Request,
    current_user: User = Depends(current_active_user),
):
    # Просто редирект на трейд-хаб, где баланс обновится (всегда актуальный)
    return RedirectResponse("/trade/ui/hub/", status_code=303)


@router.post("/trade/ui/user-balance/")
async def get_user_balance(
    user: User = Depends(current_active_user),
    balance_service: BalanceService = Depends(get_balance_service),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
):
    # Получить активный API-ключ пользователя
    apikeys = await apikeys_service.get_active(user.id)
    if not apikeys:
        return {"available": None}
    apikey = apikeys[0]
    api_key = apikey.api_key_encrypted  # если не шифруется
    api_secret = decrypt(apikey.api_secret_encrypted)
    # Получить спотовый или фьючерсный баланс, по необходимости
    balance = await balance_service.get_futures_balance(api_key, api_secret)
    return {"available": balance.get('available', None)}
