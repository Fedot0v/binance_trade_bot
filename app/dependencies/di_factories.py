from typing import TypeVar, Type

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db_dependencie import get_session
from app.services.trade_service import TradeService
from app.services.strategy_config_service import StrategyConfigService
from app.services.deal_service import DealService
from app.services.marketdata_service import MarketDataService
from app.services.apikeys_service import APIKeysService
from app.services.user_service_settings import UserSettingsService
from app.services.strategy_log_service import StrategyLogService

from app.repositories.strategy_repository import StrategyLogRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.marketdata_repository import MarketDataRepository
from app.repositories.apikeys_repository import APIKeysRepository
from app.repositories.user_repository import UserSettingsRepository
from app.repositories.strategy_config_repository import StrategyConfigRepository

from app.clients.client_factory import ExchangeClientFactory
from app.clients.binance_client import BinanceClientFactory


S = TypeVar("S")
T = TypeVar("T")


def get_repository(repo_class: Type[T]):
    def _get_repo(db: AsyncSession = Depends(get_session)) -> T:
        return repo_class(db)
    return _get_repo


def get_service(service_class: Type[S], repo_class: Type[T]):
    repo_dependency = get_repository(repo_class)
    def _get_service(
        repo: T = Depends(repo_dependency)
    ) -> S:
        return service_class(repo)
    return _get_service


get_strategy_service = get_service(StrategyConfigService, StrategyConfigRepository)
get_deal_service = get_service(DealService, DealRepository)
get_marketdata_service = get_service(MarketDataService, MarketDataRepository)
get_apikeys_service = get_service(APIKeysService, APIKeysRepository)
get_user_settings_service = get_service(UserSettingsService, UserSettingsRepository)
get_strategy_log_service = get_service(StrategyLogService, StrategyLogRepository)


# Фабрика клиента для Binance — через Depends, чтобы можно было подменить!
def get_binance_factory() -> ExchangeClientFactory:
    return BinanceClientFactory(testnet=True)  # или testnet=False для боевого режима


def get_trade_service(
    strategy_service: StrategyConfigService = Depends(get_strategy_service),
    deal_service: DealService = Depends(get_deal_service),
    marketdata_service: MarketDataService = Depends(get_marketdata_service),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
    user_settings_service: UserSettingsService = Depends(get_user_settings_service),
    log_service: StrategyLogService = Depends(get_strategy_log_service),
    exchange_client_factory: ExchangeClientFactory = Depends(get_binance_factory),
):
    return TradeService(
        strategy_service,
        deal_service,
        marketdata_service,
        apikeys_service,
        user_settings_service,
        log_service,
        exchange_client_factory,
    )
