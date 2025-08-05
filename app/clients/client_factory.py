from abc import ABC, abstractmethod


class ExchangeClientFactory(ABC):
    """
    Абстрактная фабрика клиентов для разных бирж (Binance, Bybit, Kucoin...)
    """
    @abstractmethod
    async def create(self, api_key: str, api_secret: str, **kwargs):
        """
        Возвращает асинхронного клиента для биржи.
        """
        pass
    
    async def close(self, client):
        """
        Закрывает асинхронного клиента.
        """
        pass
