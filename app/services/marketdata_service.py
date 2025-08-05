class MarketDataService:
    def __init__(self, client_factory):
        self.client_factory = client_factory
        
    async def get_klines(
        self,
        api_key,
        api_secret,
        symbol,
        interval,
        limit=100
    ):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            return await client.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
        finally:
            await self.client_factory.close(client)

    async def get_price(self, api_key, api_secret, symbol):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            data = await client.futures_symbol_ticker(symbol=symbol)
            return float(data["price"])
        finally:
            await self.client_factory.close(client)

#     async def get_ohlcv(self, api_key: str, api_secret: str, symbol: str, interval: str = "1h", limit: int = 100, testnet: bool = False) -> pd.DataFrame:
#         client = await self.client_factory.create(api_key, api_secret, testnet=testnet)
#         try:
#             klines = await client.get_klines(symbol=symbol, interval=interval, limit=limit)
#             # Binance возвращает список списков
#             df = pd.DataFrame(klines, columns=[
#                 "open_time", "open", "high", "low", "close", "volume",
#                 "close_time", "quote_asset_volume", "number_of_trades",
#                 "taker_buy_base", "taker_buy_quote", "ignore"
#             ])
#             # Приводи нужные столбцы к float/int
#             for col in ["open", "high", "low", "close", "volume"]:
#                 df[col] = df[col].astype(float)
#             df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
#             return df
#         finally:
#             await self.client_factory.close(client)
