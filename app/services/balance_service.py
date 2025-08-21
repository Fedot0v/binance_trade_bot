from clients.client_factory import ExchangeClientFactory

class BalanceService:
    def __init__(self, client_factory):
        self.client_factory: ExchangeClientFactory = client_factory

    async def get_futures_balance(self, api_key, api_secret, asset="USDT"):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            account_info = await client.futures_account_balance()
            for item in account_info:
                if item["asset"] == asset:
                    return {
                        "asset": asset,
                        "balance": float(item["balance"]),
                        "available": float(item["availableBalance"])
                    }
            return {"asset": asset, "balance": 0.0, "available": 0.0}
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
