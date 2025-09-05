import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.user_strategy_template_service import UserStrategyTemplateService
from services.deal_service import DealService
from services.strategy_config_service import StrategyConfigService
from schemas.user_strategy_template import UserStrategyTemplateRead
from models.user_model import Symbols
from app.tasks.backtest_tasks import run_backtest_task # Импортируем нашу Celery задачу

from dependencies.user_dependencies import fastapi_users
from dependencies.di_factories import get_user_strategy_template_service, get_backtest_service, get_deal_service, get_strategy_service


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
current_active_user = fastapi_users.current_user(active=True)


@router.get("/backtest/run/", response_class=HTMLResponse)
async def backtest_form(
    request: Request,
    current_user=Depends(current_active_user),
    user_strategy_template_service: UserStrategyTemplateService = Depends(
        get_user_strategy_template_service
    ),
    # backtest_service: BacktestService = Depends(get_backtest_service), # Больше не используется напрямую
    strategy_config_service: StrategyConfigService = Depends(get_strategy_service)
):
    # Получаем шаблоны стратегий пользователя
    templates_list = await user_strategy_template_service.get_all(
        current_user.id
    )
    
    # Получаем информацию о стратегиях для определения компенсационной
    strategy_configs = await strategy_config_service.get_active()
    
    # Получаем список символов из enum
    symbols_list = [symbol.value for symbol in Symbols]

    # Подготавливаем данные шаблонов с параметрами для JavaScript
    templates_with_params = []
    for template in templates_list:
        template_data = {
            "id": template.id,
            "template_name": template.template_name,
            "description": getattr(template, 'description', ''),
            "strategy_config_id": template.strategy_config_id,
            "parameters": template.parameters if hasattr(template, 'parameters') and template.parameters else {}
        }
        templates_with_params.append(template_data)

    return templates.TemplateResponse(
        "backtest/run.html",
        {
            "request": request,
            "templates": templates_list,
            "templates_data": templates_with_params,  # Передаем данные шаблонов с параметрами
            "strategy_configs": strategy_configs,  # Передаем конфигурации стратегий
            "symbols": symbols_list,  # Передаем список значений символов
            "strategies": [],  # Больше не используем встроенные стратегии
            "result": None,
            "current_user": current_user
        }
    )



@router.post("/backtest/run/", response_class=HTMLResponse)
async def backtest_run(
    request: Request,
    template_id: str = Form(...),  # Изменено на str для правильной обработки
    symbol: str = Form(default="BTCUSDT"),
    start_date: str = Form(default=None),
    end_date: str = Form(default=None),
    initial_balance: float = Form(default=10000.0),

    current_user=Depends(current_active_user),
    user_strategy_template_service: UserStrategyTemplateService = Depends(
        get_user_strategy_template_service
    ),
    deal_service: DealService = Depends(get_deal_service),
    # Дополнительные параметры (могут отсутствовать)
    custom_param_ema_fast: str = Form(default=None),
    custom_param_ema_slow: str = Form(default=None),
    custom_param_trend_threshold: str = Form(default=None),
    custom_param_deposit_prct: str = Form(default=None),
    custom_param_stop_loss_pct: str = Form(default=None),
    custom_param_take_profit_pct: str = Form(default=None),
    custom_param_btc_deposit_prct: str = Form(default=None),
    custom_param_eth_deposit_prct: str = Form(default=None),
    custom_param_btc_stop_loss_pct: str = Form(default=None),
    custom_param_eth_stop_loss_pct: str = Form(default=None),
    custom_param_trailing_stop_pct: str = Form(default=None),
    custom_param_impulse_threshold: str = Form(default=None),
    custom_param_candles_against_threshold: str = Form(default=None),
    custom_param_max_trade_duration: str = Form(default=None),
):
    try:
        # Получаем шаблон стратегии пользователя
        try:
            template_id_int = int(template_id)
        except ValueError:
            raise ValueError(f"Неверный ID шаблона: {template_id}")
        
        template = await user_strategy_template_service.get_by_id(template_id_int, current_user.id)
        if not template:
            raise ValueError(f"Шаблон стратегии с ID {template_id} не найден")

        # Собираем пользовательские параметры из формы
        custom_params = {}
        if custom_param_ema_fast: custom_params['ema_fast'] = custom_param_ema_fast
        if custom_param_ema_slow: custom_params['ema_slow'] = custom_param_ema_slow
        if custom_param_trend_threshold: custom_params['trend_threshold'] = custom_param_trend_threshold
        if custom_param_deposit_prct: custom_params['deposit_prct'] = custom_param_deposit_prct
        if custom_param_stop_loss_pct: custom_params['stop_loss_pct'] = custom_param_stop_loss_pct
        if custom_param_take_profit_pct: custom_params['take_profit_pct'] = custom_param_take_profit_pct
        if custom_param_btc_deposit_prct: custom_params['btc_deposit_prct'] = custom_param_btc_deposit_prct
        if custom_param_eth_deposit_prct: custom_params['eth_deposit_prct'] = custom_param_eth_deposit_prct
        if custom_param_btc_stop_loss_pct: custom_params['btc_stop_loss_pct'] = custom_param_btc_stop_loss_pct
        if custom_param_eth_stop_loss_pct: custom_params['eth_stop_loss_pct'] = custom_param_eth_stop_loss_pct
        if custom_param_trailing_stop_pct: custom_params['trailing_stop_pct'] = custom_param_trailing_stop_pct
        if custom_param_impulse_threshold: custom_params['impulse_threshold'] = custom_param_impulse_threshold
        if custom_param_candles_against_threshold: custom_params['candles_against_threshold'] = custom_param_candles_against_threshold
        if custom_param_max_trade_duration: custom_params['max_trade_duration'] = custom_param_max_trade_duration

        # Создаем модифицированный шаблон если есть пользовательские параметры
        if custom_params:
            print(f"🔧 Применяем пользовательские параметры: {custom_params}")
            # Создаем копию оригинального шаблона
            from types import SimpleNamespace
            modified_template = SimpleNamespace()
            modified_template.id = template.id
            modified_template.template_name = template.template_name
            modified_template.description = template.description
            modified_template.symbol = template.symbol
            modified_template.interval = template.interval
            # Получаем leverage из шаблона, если None - используем 1
            leverage_value = getattr(template, 'leverage', None)
            if leverage_value is None:
                leverage_value = 1
            modified_template.leverage = leverage_value
            modified_template.strategy_config_id = template.strategy_config_id
            modified_template.user_id = template.user_id

            # Объединяем оригинальные параметры с пользовательскими
            original_params = template.parameters or {}
            modified_template.parameters = {**original_params, **custom_params}
            template = modified_template
            print(f"✅ Модифицированный шаблон готов: {modified_template.parameters}")

        templates_list = await user_strategy_template_service.get_all(current_user.id)
        
        # Подготавливаем параметры для бектеста
        if not start_date or not end_date:
            raise ValueError("Для скачивания данных нужны даты начала и окончания")
        
        # Используем интервал из шаблона стратегии
        interval = template.interval or "1m"  # По умолчанию 1 минута
        
        # Используем универсальный бэктест
        print(f"🎯 Запуск УНИВЕРСАЛЬНОГО бэктеста для шаблона {template.template_name} (запускается как Celery задача)")
        print(f"  📊 Strategy Config ID: {template.strategy_config_id}")
        print(f"  📅 Период: {start_date} - {end_date}")
        print(f"  💰 Баланс: ${initial_balance}")

        # LegacyBacktestService больше не нужен здесь, так как логика перенесена в Celery задачу
        # legacy_service = LegacyBacktestService()

        compensation_strategy_flag = False
        if template.strategy_config_id == 2:  # ID компенсационной стратегии
            compensation_strategy_flag = True
            # Для компенсационной стратегии проверяем оба символа
            btc_open_deal = await deal_service.get_open_deal_for_user_and_symbol(
                current_user.id, "BTCUSDT"
            )
            eth_open_deal = await deal_service.get_open_deal_for_user_and_symbol(
                current_user.id, "ETHUSDT"
            )

            print(f"  🔍 Проверка открытых сделок:")
            print(f"    BTC: {'Есть' if btc_open_deal else 'Нет'}")
            print(f"    ETH: {'Есть' if eth_open_deal else 'Нет'}")

            if btc_open_deal:
                raise ValueError("У вас уже есть открытая сделка по BTCUSDT")
            if eth_open_deal:
                raise ValueError("У вас уже есть открытая сделка по ETHUSDT")

        # Определяем символ(ы) для передачи в Celery задачу
        # Если это компенсационная стратегия, передаем оба символа, иначе - символ из формы.
        task_symbols = ["BTCUSDT", "ETHUSDT"] if compensation_strategy_flag else symbol
        
        print(f"DEBUG_UI: Symbol from form: {symbol}")
        print(f"DEBUG_UI: task_symbols to Celery: {task_symbols}")

        # Запускаем Celery задачу
        task = run_backtest_task.delay(
            user_id=str(current_user.id),
            template_id=template.id,
            symbol=task_symbols,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            leverage=getattr(template, 'leverage', None) or 1,
            strategy_config_id=template.strategy_config_id,
            compensation_strategy=compensation_strategy_flag,
            custom_params=custom_params
        )
        print(f"✅ Бэктест запущен как Celery задача! ID задачи: {task.id}")
        
        # Получаем список символов для отображения формы
        symbols_list = [symbol.value for symbol in Symbols]
        
        # Подготавливаем данные шаблонов с параметрами для JavaScript
        templates_with_params = []
        for template_item in templates_list:
            template_data = {
                "id": template_item.id,
                "template_name": template_item.template_name,
                "description": getattr(template_item, 'description', ''),
                "strategy_config_id": template_item.strategy_config_id,
                "parameters": template_item.parameters if hasattr(template_item, 'parameters') and template_item.parameters else {}
            }
            templates_with_params.append(template_data)

        return templates.TemplateResponse(
            "backtest/run.html",
            {
                "request": request,
                "templates": templates_list,
                "templates_data": templates_with_params,
                "symbols": symbols_list,
                "strategies": [],
                "result": {"message": f"Бэктест запущен в фоновом режиме. ID задачи: {task.id}", "task_id": task.id},
                "current_user": current_user,
                "error": None
            }
        )
        
    except Exception as e:
        # В случае ошибки также передаем символы
        templates_list = await user_strategy_template_service.get_all(current_user.id)
        symbols_list = [symbol.value for symbol in Symbols]

        # Подготавливаем данные шаблонов с параметрами для JavaScript
        templates_with_params = []
        for template in templates_list:
            template_data = {
                "id": template.id,
                "template_name": template.template_name,
                "description": getattr(template, 'description', ''),
                "strategy_config_id": template.strategy_config_id,
                "parameters": template.parameters if hasattr(template, 'parameters') and template.parameters else {}
            }
            templates_with_params.append(template_data)

        return templates.TemplateResponse(
            "backtest/run.html",
            {
                "request": request,
                "templates": templates_list,
                "templates_data": templates_with_params,  # Передаем данные шаблонов с параметрами
                "symbols": symbols_list,  # Передаем символы даже при ошибке
                "strategies": [],
                "result": None,
                "current_user": current_user,
                "error": str(e)
            }
        )