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


def build_trade_service(session, *, testnet=True):
    # Клиент биржи
    exchange_client_factory = BinanceClientFactory(testnet=testnet)

    # Репозитории
    deal_repo = DealRepository(session)
    log_repo = StrategyLogRepository(session)
    template_repo = UserStrategyTemplateRepository(session)
    strategy_config_repo = StrategyConfigRepository(session)
    apikeys_repo = APIKeysRepository(session)
    bot_repo = UserBotRepository(session)

    # Сервисы
    strategy_service = StrategyConfigService(strategy_config_repo)
    deal_service = DealService(deal_repo)
    marketdata_service = MarketDataService(exchange_client_factory)
    apikeys_service = APIKeysService(apikeys_repo)
    user_strategy_template_service = UserStrategyTemplateService(template_repo)
    log_service = StrategyLogService(log_repo)
    balance_service = BalanceService(exchange_client_factory)
    order_service = OrderService(exchange_client_factory)
    userbot_service = UserBotService(bot_repo)

    # Обрати внимание на порядок аргументов!
    trade_service = TradeService(
        base_strategy=strategy_service,                        # 1. strategy_service
        deal_service=deal_service,                            # 2. deal_service
        marketdata_service=marketdata_service,                      # 3. marketdata_service
        apikeys_service=apikeys_service,                         # 4. apikeys_service
        user_strategy_template_service=user_strategy_template_service,          # 5. user_strategy_template_service
        log_service=log_service,                             # 6. log_service
        exchange_client_factory=exchange_client_factory,                 # 7. exchange_client_factory
        balance_service=balance_service,         # 8. balance_service (named)
        order_service=order_service,             # 9. order_service (named)
        strategy_config_service=strategy_service,  # 10. strategy_config_service (named, если он совпадает со strategy_service)
        userbot_service=userbot_service           # 11. userbot_service (named)
    )
    return trade_service


def build_deal_service(session, *, testnet=True):
    exchange_client_factory = BinanceClientFactory(testnet=testnet)
    deal_repo = DealRepository(session)
    apikeys_repo = APIKeysRepository(session)
    apikeys_service = APIKeysService(apikeys_repo)
    log_service = StrategyLogService(StrategyLogRepository(session))

    deal_service = DealService(
        deal_repo, exchange_client_factory, apikeys_service,
        log_service
    )

    return deal_service
