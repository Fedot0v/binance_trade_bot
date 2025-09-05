from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dependencies.user_dependencies import fastapi_users
from dependencies.di_factories import get_backtest_result_service # Импортируем нашу зависимость
from services.backtest_result_service import BacktestResultService
from schemas.backtest import BacktestResult # Используем BacktestResult для отображения, если нужно
from schemas.backtest_result import BacktestResultRead # Схема для чтения из базы
from services.user_strategy_template_service import UserStrategyTemplateService
from repositories.user_repository import UserStrategyTemplateRepository
from dependencies.db_dependencie import get_session
from sqlalchemy.ext.asyncio import AsyncSession

# Фабрика для UserStrategyTemplateService
async def get_user_strategy_template_service(session: AsyncSession = Depends(get_session)) -> UserStrategyTemplateService:
    user_strategy_template_repo = UserStrategyTemplateRepository(session)
    return UserStrategyTemplateService(user_strategy_template_repo)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
current_active_user = fastapi_users.current_user(active=True)

@router.get("/backtest/results/{task_id}", response_class=HTMLResponse)
async def get_backtest_results(
    request: Request,
    task_id: str,
    current_user=Depends(current_active_user),
    backtest_result_service: BacktestResultService = Depends(get_backtest_result_service),
    user_strategy_template_service: UserStrategyTemplateService = Depends(get_user_strategy_template_service)
):
    backtest_record = await backtest_result_service.get_result_by_task_id(task_id)
    if not backtest_record or backtest_record.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Результаты бэктеста не найдены или нет доступа")

    # Определяем, какие данные передать в шаблон
    status = backtest_record.status
    results_data = backtest_record.results
    error = None

    results: Optional[BacktestResult] = None
    if status == "completed" and results_data:
        try:
            results = BacktestResult.model_validate(results_data) # Преобразуем словарь в модель
        except Exception as e:
            error = f"Ошибка валидации результатов бэктеста: {e}"
            status = "failed" # Помечаем как failed, если валидация не удалась

    template_name: Optional[str] = None
    if backtest_record.template_id:
        template = await user_strategy_template_service.get_by_id(
            backtest_record.template_id, current_user.id
        )
        if template:
            template_name = template.template_name

    if status == "failed" and results_data and "error" in results_data:
        error = results_data["error"]

    return templates.TemplateResponse(
        "backtest/results.html", # Нужен новый шаблон для отображения результатов
        {
            "request": request,
            "current_user": current_user,
            "task_id": task_id,
            "status": status,
            "results": results.model_dump(mode='json') if results else None, # Теперь это модель BacktestResult
            "error": error,
            "created_at": backtest_record.created_at,
            "completed_at": backtest_record.completed_at,
            "template_name": template_name
        }
    )

@router.get("/api/backtest/results/{task_id}", response_model=BacktestResultRead)
async def get_backtest_results_api(
    task_id: str,
    current_user=Depends(current_active_user),
    backtest_result_service: BacktestResultService = Depends(get_backtest_result_service)
):
    backtest_record = await backtest_result_service.get_result_by_task_id(task_id)
    if not backtest_record or backtest_record.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Результаты бэктеста не найдены или нет доступа")
    
    return backtest_record
