class OrderService:
    def __init__(self, client_factory):
        self.client_factory = client_factory

    async def create_order(
        self,
        api_key,
        api_secret,
        symbol,
        side,
        quantity,
        price=None,
        leverage=1,
        order_type="MARKET"
    ):
        # Проверяем, что quantity корректный
        if not quantity or quantity <= 0:
            raise ValueError(f"Некорректное количество для ордера: {quantity}")
        
        client = await self.client_factory.create(api_key, api_secret)
        try:
            await client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            params = dict(
                symbol=symbol,
                side=side,
                quantity=quantity,
                type=order_type
            )
            if price and order_type == "LIMIT":
                params["price"] = price
                params["timeInForce"] = "GTC"
            result = await client.futures_create_order(**params)
            return result
        finally:
            await self.client_factory.close(client)

    async def get_order_status(self, api_key, api_secret, symbol, order_id):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            return await client.futures_get_order(
                symbol=symbol,
                orderId=order_id
            )
        finally:
            await self.client_factory.close(client)

    async def cancel_order(self, api_key, api_secret, symbol, order_id):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            return await client.futures_cancel_order(
                symbol=symbol,
                orderId=order_id
            )
        finally:
            await self.client_factory.close(client)
            
    async def get_open_orders(self, api_key, api_secret, symbol):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            return await client.futures_get_open_orders(symbol=symbol)
        finally:
            await self.client_factory.close(client)

    async def get_order_history(self, api_key, api_secret, symbol, limit=50):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            return await client.futures_get_all_orders(
                symbol=symbol,
                limit=limit
            )
        finally:
            await self.client_factory.close(client)

    async def close_position(self, api_key, api_secret, symbol, side, quantity):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            result = await client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                reduceOnly=True
            )
            return result
        finally:
            await self.client_factory.close(client)

    async def get_position(self, api_key, api_secret, symbol):
        client = await self.client_factory.create(api_key, api_secret)
        try:
            positions = await client.futures_position_information(
                symbol=symbol
            )
            for pos in positions:
                if pos['symbol'] == symbol:
                    return pos
            return None
        finally:
            await self.client_factory.close(client)
