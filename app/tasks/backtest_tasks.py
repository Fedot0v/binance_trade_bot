from celery_app import celery_app
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
import asyncio
from typing import Dict, Any, List, Union
from uuid import UUID
from datetime import datetime
import pandas as pd

from services.backtest.universal_backtest_service import UniversalBacktestService
from services.backtest.legacy_strategy_adapter import LegacyBacktestService
from services.user_strategy_template_service import UserStrategyTemplateService
from services.deal_service import DealService
from services.strategy_config_service import StrategyConfigService
from repositories.user_repository import UserStrategyTemplateRepository
from repositories.deal_repository import DealRepository
from repositories.strategy_config_repository import StrategyConfigRepository
from repositories.apikeys_repository import APIKeysRepository
from repositories.strategy_repository import StrategyLogRepository
from services.apikeys_service import APIKeysService
from services.strategy_log_service import StrategyLogService
from clients.binance_client import BinanceClientFactory
from schemas.backtest import BacktestResult
from services.csv_data_service import CSVDataService
from services.csv_loader_service import CSVLoaderService
from repositories.backtest_result_repository import BacktestResultRepository
from services.backtest_result_service import BacktestResultService


def get_async_session_maker():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    engine = create_async_engine(DATABASE_URL, echo=False)
    return sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

def build_universal_backtest_service(session=None) -> UniversalBacktestService:
    csv_service = CSVDataService()
    csv_loader = CSVLoaderService()
    return UniversalBacktestService(csv_service=csv_service, csv_loader=csv_loader)

def convert_timestamps_to_datetime(obj):
    if isinstance(obj, dict):
        return {k: convert_timestamps_to_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_timestamps_to_datetime(elem) for elem in obj]
    elif isinstance(obj, pd.Timestamp):
        return obj.to_pydatetime()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj

def sanitize_json_values(obj):
    """Рекурсивно заменяет недопустимые для JSON значения (NaN/Infinity) на None/строки."""
    import math
    if isinstance(obj, dict):
        return {k: sanitize_json_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_json_values(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, str):
        if obj in ("Infinity", "-Infinity", "NaN"):
            return None
        return obj
    return obj

@celery_app.task(bind=True, name='app.tasks.backtest_tasks.run_backtest_task')
def run_backtest_task(
    self,
    user_id: str,
    template_id: int,
    symbol: Union[str, List[str]],
    start_date: str,
    end_date: str,
    initial_balance: float,
    leverage: int,
    strategy_config_id: int,
    compensation_strategy: bool = False,
    custom_params: Dict[str, Any] = None
):
    print("DEBUG: Celery task run_backtest_task started.")
    async def main():
        print("DEBUG: Starting backtest task main function.")
        async_session = get_async_session_maker()
        print("DEBUG: Async session maker created.")
        async with async_session() as session:
            print("DEBUG: Async session opened.")
            # Initialize services
            user_strategy_template_repo = UserStrategyTemplateRepository(session)
            user_strategy_template_service = UserStrategyTemplateService(user_strategy_template_repo)
            print("DEBUG: UserStrategyTemplateService initialized.")
            
            deal_repo = DealRepository(session)
            testnet_env = os.environ.get("BINANCE_TESTNET", "false").lower() == "true"
            exchange_client_factory = BinanceClientFactory(testnet=testnet_env)
            apikeys_repo = APIKeysRepository(session)
            apikeys_service = APIKeysService(apikeys_repo)
            log_repo = StrategyLogRepository(session)
            log_service = StrategyLogService(log_repo)
            deal_service = DealService(deal_repo, exchange_client_factory, apikeys_service, log_service)
            print("DEBUG: DealService and related services initialized.")

            strategy_config_repo = StrategyConfigRepository(session)
            strategy_config_service = StrategyConfigService(strategy_config_repo)
            print("DEBUG: StrategyConfigService initialized.")

            # Initialize services for saving backtest results
            backtest_result_repo = BacktestResultRepository(session)
            backtest_result_service = BacktestResultService(backtest_result_repo)
            print("DEBUG: BacktestResultService initialized.")

            # Create initial backtest record in the database
            print("DEBUG: Attempting to create initial backtest record.")
            try:
                await backtest_result_service.create_result(self.request.id, template_id, UUID(user_id))
                await session.commit() # Save initial status
                print(f"DEBUG: Initial backtest record created for task ID {self.request.id}.")
            except Exception as e:
                print(f"ERROR: Error creating initial backtest record: {e}")
                # Continue if initial record could not be saved, but this is undesirable
                return

            print("DEBUG: Fetching strategy template.")
            try:
                # Get strategy template
                template = await user_strategy_template_service.get_by_id(template_id, UUID(user_id))
                if not template:
                    print(f"ERROR: Strategy template with ID {template_id} not found for user {user_id}")
                    await backtest_result_service.update_result_status(self.request.id, "failed", {"error": "Strategy template not found"})
                    await session.commit()
                    return
                print(f"DEBUG: Strategy template {template_id} fetched.")

                # If template is a dict, convert it to SimpleNamespace
                if isinstance(template, dict):
                    print("DEBUG: Converting template from dict to SimpleNamespace.")
                    from types import SimpleNamespace
                    template = SimpleNamespace(**template)
                    print("DEBUG: Template converted.")

                # Apply custom parameters, if any
                if custom_params:
                    print("DEBUG: Applying custom parameters.")
                    from types import SimpleNamespace
                    modified_template = SimpleNamespace()
                    modified_template.id = template.id
                    modified_template.template_name = template.template_name
                    modified_template.description = template.description
                    modified_template.symbol = symbol # Используем символ из параметров задачи
                    modified_template.interval = template.interval
                    # Получаем leverage из шаблона, если None - используем 1
                    modified_template.leverage = leverage # Use leverage from task parameters
                    modified_template.strategy_config_id = template.strategy_config_id
                    modified_template.user_id = template.user_id
                    
                    original_params = getattr(template, 'parameters', {}) or {} # Use getattr for safety
                    modified_template.parameters = {**original_params, **custom_params}
                    template = modified_template
                    print(f"DEBUG: Модифицированный шаблон готов: {modified_template.parameters}")
                else:
                    # Если нет пользовательских параметров, просто обновляем символ в шаблоне
                    template.symbol = symbol

                # Backtest isolation: do NOT check live DB deals; backtest has its own state
                if compensation_strategy:
                    print("DEBUG: Skipping live DB open-trades check for compensation strategy in backtest mode.")

                # Use UniversalBacktestService aligned with online logic
                result: BacktestResult
                if compensation_strategy:
                    from strategies.strategy_factory import make_strategy
                    universal_service = build_universal_backtest_service(session)
                    # Build the same adapter used online
                    strategy = make_strategy('compensation', template)
                    symbols_list = symbol if isinstance(symbol, list) else ['BTCUSDT', 'ETHUSDT']
                    try:
                        print(f"DEBUG: Effective params (compensation): {getattr(template, 'parameters', {})}")
                    except Exception:
                        pass
                    print(f"🎯 Starting universal compensation backtest (online-aligned) for template {template.template_name}")
                    result = await universal_service.run_compensation_backtest(
                        strategy=strategy,
                        template=template,
                        symbols=symbols_list,
                        data_source='download',
                        start_date=start_date,
                        end_date=end_date,
                        initial_balance=initial_balance,
                        config=None
                    )
                else:
                    # Align regular strategy backtest with online logic as well
                    from strategies.strategy_factory import make_strategy
                    universal_service = build_universal_backtest_service(session)
                    strategy = make_strategy('novichok', template)
                    # Normalize symbol list
                    symbols_list = symbol if isinstance(symbol, list) else [symbol]
                    try:
                        print(f"DEBUG: Effective params (novichok): {getattr(template, 'parameters', {})}")
                    except Exception:
                        pass
                    print(f"🎯 Starting universal regular backtest (online-aligned) for template {template.template_name}")
                    result = await universal_service.run_backtest(
                        strategy=strategy,
                        template=template,
                        symbols=symbols_list,
                        data_source='download',
                        start_date=start_date,
                        end_date=end_date,
                        initial_balance=initial_balance,
                        config=None
                    )
                
                print(f"DEBUG: Backtest result equity_curve size: {len(result.equity_curve)}")
                print(f"DEBUG: Backtest result equity_curve: {result.equity_curve[:5]}...{result.equity_curve[-5:]}" if len(result.equity_curve) > 10 else f"DEBUG: Backtest result equity_curve: {result.equity_curve}")
                
                # Save backtest results to database
                processed_results = convert_timestamps_to_datetime(result.model_dump(mode='json'))
                processed_results = sanitize_json_values(processed_results)
                await backtest_result_service.update_result_status(
                    self.request.id, "completed", processed_results
                )
                await session.commit()
                print(f"✅ Backtest completed successfully in Celery! Final balance: {result.final_balance:.2f}")

            except Exception as e:
                print(f"ERROR: Exception during backtest execution: {e}")
                await session.rollback() # Rollback transaction before updating status
                await backtest_result_service.update_result_status(self.request.id, "failed", {"error": str(e)})
                await session.commit()
                print(f"❌ Error executing backtest in Celery: {e}")
                raise # Re-raise exception for Celery to mark the task as FAILED
    
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"CRITICAL ERROR in Celery task run_backtest_task: {e}")
        # Здесь можно также попытаться обновить статус задачи в БД до 'failed'
        # Но это может быть сложно, если сессия БД еще не инициализирована или уже закрыта.
        raise
