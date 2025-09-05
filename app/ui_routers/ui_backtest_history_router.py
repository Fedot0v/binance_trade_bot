from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from dependencies.db_dependencie import get_session
from dependencies.user_dependencies import fastapi_users
from models.user_model import User
from schemas.backtest_result import BacktestResultRead
from services.backtest_result_service import BacktestResultService
from dependencies.di_factories import get_backtest_result_service


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

get_current_active_user = fastapi_users.current_user(active=True)


@router.get("/backtest/history/", response_class=HTMLResponse, summary="Display backtest history")
async def backtest_history(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    backtest_result_service: BacktestResultService = Depends(get_backtest_result_service)
):
    """
    Displays an HTML page with a list of all backtests for the current user.
    """
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    backtests: List[BacktestResultRead] = await backtest_result_service.get_all_results_by_user(
        user_id=current_user.id
    )

    return templates.TemplateResponse(
        "backtest/history.html",
        {"request": request, "current_user": current_user, "backtests": backtests}
    )
