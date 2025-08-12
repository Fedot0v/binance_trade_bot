from clients.binance_client import BinanceClientFactory
from clients.client_factory import ExchangeClientFactory


def get_factory_by_name(exchange: str) -> ExchangeClientFactory:
    if exchange == "binance":
        return BinanceClientFactory(testnet=False)
    else:
        raise ValueError("Unknown exchange")
