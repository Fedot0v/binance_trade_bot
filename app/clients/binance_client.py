from binance import AsyncClient

from app.clients.client_factory import ExchangeClientFactory


class BinanceClientFactory(ExchangeClientFactory):
    def __init__(self, testnet: bool = False):
        self.testnet = testnet

    async def create(self, api_key: str, api_secret: str, **kwargs) -> AsyncClient:
        client = await AsyncClient.create(
            api_key=api_key,
            api_secret=api_secret,
            testnet=self.testnet
        )
        return client
