import os
from clients.binance_client import BinanceClientFactory
from clients.client_factory import ExchangeClientFactory


def get_factory_by_name(exchange: str) -> ExchangeClientFactory:
    if exchange == "binance":
        testnet = os.environ.get("BINANCE_TESTNET", "false").lower() == "true"
        return BinanceClientFactory(testnet=testnet)
    else:
        raise ValueError("Unknown exchange")
