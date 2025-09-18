from services.trade_service import TradeService
from services.deal_service import DealService
from services.strategy_log_service import StrategyLogService
from services.user_strategy_template_service import UserStrategyTemplateService
from services.strategy_config_service import StrategyConfigService
from services.marketdata_service import MarketDataService
from services.apikeys_service import APIKeysService
from services.bot_service import UserBotService
from services.order_service import OrderService
from services.balance_service import BalanceService

from repositories.deal_repository import DealRepository
from repositories.strategy_repository import StrategyLogRepository
from repositories.user_repository import UserStrategyTemplateRepository
from repositories.strategy_config_repository import StrategyConfigRepository
from repositories.apikeys_repository import APIKeysRepository
from repositories.bot_repository import UserBotRepository

from clients.binance_client import BinanceClientFactory
import os


def build_trade_service(session, *, testnet: bool | None = None):
    testnet_env = os.environ.get("BINANCE_TESTNET", "false").lower() == "true"
    effective_testnet = testnet if testnet is not None else testnet_env
    exchange_client_factory = BinanceClientFactory(testnet=effective_testnet)

    deal_repo = DealRepository(session)
    log_repo = StrategyLogRepository(session)
    template_repo = UserStrategyTemplateRepository(session)
    strategy_config_repo = StrategyConfigRepository(session)
    apikeys_repo = APIKeysRepository(session)
    bot_repo = UserBotRepository(session)

    strategy_service = StrategyConfigService(strategy_config_repo)
    deal_service = DealService(deal_repo)
    marketdata_service = MarketDataService(exchange_client_factory)
    apikeys_service = APIKeysService(apikeys_repo)
    user_strategy_template_service = UserStrategyTemplateService(template_repo)
    log_service = StrategyLogService(log_repo)
    balance_service = BalanceService(exchange_client_factory)
    order_service = OrderService(exchange_client_factory)
    userbot_service = UserBotService(bot_repo)

    trade_service = TradeService(
        deal_service=deal_service,                            
        marketdata_service=marketdata_service,                      
        apikeys_service=apikeys_service,                         
        user_strategy_template_service=user_strategy_template_service,
        log_service=log_service,
        exchange_client_factory=exchange_client_factory,
        balance_service=balance_service,
        order_service=order_service,
        strategy_config_service=strategy_service,
        userbot_service=userbot_service
    )
    return trade_service


def build_deal_service(session, *, testnet: bool | None = None):
    testnet_env = os.environ.get("BINANCE_TESTNET", "false").lower() == "true"
    effective_testnet = testnet if testnet is not None else testnet_env
    exchange_client_factory = BinanceClientFactory(testnet=effective_testnet)
    deal_repo = DealRepository(session)
    apikeys_repo = APIKeysRepository(session)
    apikeys_service = APIKeysService(apikeys_repo)
    log_service = StrategyLogService(StrategyLogRepository(session))

    deal_service = DealService(
        deal_repo, exchange_client_factory, apikeys_service,
        log_service
    )

    # Подключаем StrategyManager, чтобы Celery-таски могли обновлять трейлинг-стопы/выходы
    try:
        from services.strategy_manager import StrategyManager
        strategy_manager = StrategyManager(deal_service, log_service)
        deal_service.strategy_manager = strategy_manager
        print("[INIT] StrategyManager подключен в build_deal_service (Celery path)")
    except Exception as e:
        print(f"[INIT] Не удалось подключить StrategyManager: {e}")

    return deal_service
