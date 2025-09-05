from clients.client_factory import ExchangeClientFactory

class BalanceService:
    def __init__(self, client_factory):
        self.client_factory: ExchangeClientFactory = client_factory

    async def get_futures_balance(self, api_key, api_secret, asset="USDT"):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            print(f"🔍 Диагностика баланса: asset={asset}")
            account_info = await client.futures_account_balance()
            print(f"📊 Получен account_info: {account_info}")
            
            for item in account_info:
                print(f"💰 Баланс {item['asset']}: balance={item['balance']}, available={item['availableBalance']}")
                if item["asset"] == asset:
                    result = {
                        "asset": asset,
                        "balance": float(item["balance"]),
                        "available": float(item["availableBalance"])
                    }
                    print(f"✅ Найден баланс {asset}: {result}")
                    return result
            
            print(f"❌ Баланс {asset} не найден в account_info")
            return {"asset": asset, "balance": 0.0, "available": 0.0}
        except Exception as e:
            print(f"❌ Ошибка при получении баланса: {e}")
            raise
        finally:
            await self.client_factory.close(client)

    async def get_spot_balance(self, api_key, api_secret, asset="USDT"):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            account_info = await client.get_account()
            for item in account_info["balances"]:
                if item["asset"] == asset:
                    return {
                        "asset": asset,
                        "balance": float(item["free"]) + float(item["locked"]),
                        "available": float(item["free"])
                    }
            return {"asset": asset, "balance": 0.0, "available": 0.0}
        finally:
            await self.client_factory.close(client)
