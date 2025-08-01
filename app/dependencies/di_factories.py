from typing import TypeVar, Type

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db_dependencie import get_session
from services.trade_service import TradeService
from services.strategy_config_service import StrategyConfigService
from services.deal_service import DealService
from services.marketdata_service import MarketDataService
from services.apikeys_service import APIKeysService
from services.user_strategy_template_service import UserStrategyTemplateService
from services.strategy_log_service import StrategyLogService
from services.order_service import OrderService
from services.balance_service import BalanceService
from services.bot_service import UserBotService

from repositories.strategy_repository import StrategyLogRepository
from repositories.deal_repository import DealRepository
from repositories.apikeys_repository import APIKeysRepository
from repositories.user_repository import UserStrategyTemplateRepository
from repositories.strategy_config_repository import StrategyConfigRepository
from repositories.bot_repository import UserBotRepository

from clients.client_factory import ExchangeClientFactory
from clients.binance_client import BinanceClientFactory


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


def get_binance_factory() -> ExchangeClientFactory:
    return BinanceClientFactory(testnet=True)


get_strategy_service = get_service(
    StrategyConfigService,
    StrategyConfigRepository
)
get_apikeys_service = get_service(APIKeysService, APIKeysRepository)
get_user_strategy_template_service = get_service(
    UserStrategyTemplateService,
    UserStrategyTemplateRepository
)
get_strategy_log_service = get_service(
    StrategyLogService,
    StrategyLogRepository
)
get_userbot_service = get_service(UserBotService, UserBotRepository)


def get_deal_service(
    repo: DealRepository = Depends(get_repository(DealRepository)),
    binance_client: BinanceClientFactory = Depends(get_binance_factory),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
    log_service: StrategyLogService = Depends(get_strategy_log_service)
):
    return DealService(repo, binance_client, apikeys_service, log_service)


def get_marketdata_service(
    binance_client: BinanceClientFactory = Depends(get_binance_factory),
) -> MarketDataService:
    return MarketDataService(binance_client)


def get_order_service(
    exchange_client_factory: ExchangeClientFactory = Depends(
        get_binance_factory
    )
) -> OrderService:
    return OrderService(exchange_client_factory)


def get_balance_service(
    exchange_client_factory: ExchangeClientFactory = Depends(
        get_binance_factory
    )
) -> BalanceService:
    return BalanceService(exchange_client_factory)


def get_trade_service(
    strategy_service: StrategyConfigService = Depends(get_strategy_service),
    deal_service: DealService = Depends(get_deal_service),
    marketdata_service: MarketDataService = Depends(get_marketdata_service),
    apikeys_service: APIKeysService = Depends(get_apikeys_service),
    user_strategy_template_service: UserStrategyTemplateService = Depends(
        get_user_strategy_template_service
    ),
    log_service: StrategyLogService = Depends(get_strategy_log_service),
    exchange_client_factory: ExchangeClientFactory = Depends(
        get_binance_factory
    ),
    balance_service: BalanceService = Depends(get_balance_service),
    order_service: OrderService = Depends(get_order_service),
    strategy_config_service: StrategyConfigService = Depends(
        get_strategy_service
    ),
    userbot_service: UserBotService = Depends(get_userbot_service)
):
    return TradeService(
        strategy_service,
        deal_service,
        marketdata_service,
        apikeys_service,
        user_strategy_template_service,
        log_service,
        exchange_client_factory,
        balance_service=balance_service,
        order_service=order_service,
        strategy_config_service=strategy_config_service,
        userbot_service=userbot_service
    )
