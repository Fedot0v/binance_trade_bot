import logging
from binance import AsyncClient
from clients.client_factory import ExchangeClientFactory


class BinanceClientFactory(ExchangeClientFactory):
    """
    Фабрика для создания клиента Binance.

    Args:
        testnet (bool): Указывает, использовать ли тестовую сеть Binance.
    """
    def __init__(self, testnet: bool = False):
        self.testnet = testnet
        self.logger = logging.getLogger(__name__)

    async def create(self, api_key: str, api_secret: str, **kwargs) -> AsyncClient:
        """
        Создает асинхронный клиент Binance.

        Args:
            api_key (str): API ключ Binance.
            api_secret (str): Секретный ключ Binance.
            **kwargs: Дополнительные параметры.

        Returns:
            AsyncClient: Экземпляр клиента Binance.

        Raises:
            Exception: Если создание клиента завершилось ошибкой.
        """
        try:
            testnet = kwargs.get("testnet", self.testnet)
            client = await AsyncClient.create(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet
            )
            self.logger.info("Binance клиент успешно создан.")
            return client
        except Exception as e:
            self.logger.exception(f"Ошибка при создании Binance клиента: {str(e)}")
            raise

    async def close(self, client: AsyncClient):
        """
        Закрывает асинхронный клиент Binance.

        Args:
            client (AsyncClient): Экземпляр клиента Binance.

        Raises:
            Exception: Если закрытие клиента завершилось ошибкой.
        """
        try:
            await client.close_connection()
            self.logger.info("Binance клиент успешно закрыт.")
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии Binance клиента: {str(e)}")
            raise

    async def futures_get_order(self, client, symbol: str, order_id: int):
        return await client.futures_get_order(symbol=symbol, orderId=order_id)

    async def futures_cancel_order(self, client, symbol: str, order_id: int):
        return await client.futures_cancel_order(symbol=symbol, orderId=order_id)

    async def futures_create_order(self, client, **kwargs):
        return await client.futures_create_order(**kwargs)