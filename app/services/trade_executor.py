from uuid import UUID
import asyncio
from typing import Optional

from clients.client_factory import ExchangeClientFactory
from services.apikeys_service import APIKeysService
from services.balance_service import BalanceService
from services.order_service import OrderService
from services.deal_service import DealService
from services.strategy_log_service import StrategyLogService
from services.marketdata_service import MarketDataService
from schemas.deal import DealCreate
from schemas.strategy_log import StrategyLogCreate
from strategies.contracts import OrderIntent


class TradeExecutor:
    """Responsible only for executing trading decisions."""
    
    def __init__(
        self,
        exchange_client_factory: ExchangeClientFactory,
        balance_service: BalanceService,
        order_service: OrderService,
        deal_service: DealService,
        log_service: StrategyLogService,
        apikeys_service: APIKeysService,
        marketdata_service: MarketDataService # Add marketdata_service
    ):
        self.exchange_client_factory = exchange_client_factory
        self.balance_service = balance_service
        self.order_service = order_service
        self.deal_service = deal_service
        self.log_service = log_service
        self.apikeys_service = apikeys_service
        self.marketdata_service = marketdata_service # Store instance

    async def execute_intent(
        self,
        intent: OrderIntent,
        template,
        user_id: UUID,
        bot_id: UUID,
        api_key: str,
        api_secret: str,
        session,
        strategy=None
    ):
        """Executes a single trading intent."""
        print(f"Executing intent: {intent}")
        
        last_price = await self._get_last_price(api_key, api_secret, intent.symbol, template.interval.value)
        
        quantity = await self._calculate_quantity(intent, last_price, api_key, api_secret)
        
        order_result = await self._place_order(
            api_key, api_secret, template, intent, quantity
        )
        
        entry_price = await self._fetch_entry_price(api_key, api_secret, intent.symbol, order_result['orderId'])
        
        await self._record_deal(
            user_id, bot_id, template, entry_price, order_result, intent, 
            quantity, session, strategy
        )

    async def _get_last_price(self, api_key: str, api_secret: str, symbol: str, interval: str) -> float:
        """Retrieves the last price for a symbol."""
        marketdata_service = self.marketdata_service 
        
        klines = await marketdata_service.get_klines(
            api_key, api_secret, symbol=symbol, interval=interval, limit=1
        )
        if not klines:
            raise ValueError(f"Failed to get data for {symbol}")
        
        return float(klines[0][4])

    async def _calculate_quantity(self, intent: OrderIntent, last_price: float, api_key: str, api_secret: str) -> float:
        """Calculates the quantity for an order."""
        sizing = intent.sizing
        
        if sizing == "risk_pct":
            balance_data = await self.balance_service.get_futures_balance(api_key, api_secret, asset="USDT")
            balance = balance_data["available"]
            usd_size = balance * intent.size
        elif sizing == "usd":
            usd_size = intent.size
        elif sizing == "qty":
            return intent.size
        else:
            raise ValueError(f"Unknown sizing: {sizing}")
        
        if usd_size <= 0:
            raise ValueError(f"Invalid position size: {usd_size}")
        
        quantity = round(usd_size / last_price, 3)
        if quantity <= 0:
            raise ValueError(f"Invalid quantity: {quantity}")
        
        print(f"Calculated: quantity={quantity} (size={usd_size}/price={last_price})")
        return quantity

    async def _place_order(self, api_key: str, api_secret: str, template, intent: OrderIntent, quantity: float):
        """Creates an order on the exchange."""
        if not quantity or quantity <= 0:
            raise ValueError(f"Invalid quantity for order: {quantity}")
        
        order_side = intent.side
        print(f"Creating order: symbol={intent.symbol}, side={order_side}, quantity={quantity}, leverage={template.leverage}")
        
        result = await self.order_service.create_order(
            api_key, api_secret,
            symbol=intent.symbol,
            side=order_side,
            quantity=quantity,
            leverage=int(template.leverage),
            order_type="MARKET"
        )
        print(f"Order created: {result}")
        return result

    async def _fetch_entry_price(self, api_key: str, api_secret: str, symbol: str, order_id: str) -> float:
        """Retrieves the entry price from an executed order."""
        print(f"Fetching entry_price for order: symbol={symbol}, orderId={order_id}")
        
        client = await self.exchange_client_factory.create(api_key, api_secret, exchange="binance")
        max_retries = 5
        entry_price = 0.0
        
        for i in range(max_retries):
            order_info = await client.futures_get_order(symbol=symbol, orderId=order_id)
            print(f"Order info ({i+1}): {order_info}")
            
            avg_price = float(order_info.get("avgPrice") or 0.0)
            executed_qty = float(order_info.get("executedQty") or 0.0)
            cum_quote = float(order_info.get("cumQuote") or 0.0)
            
            entry_price = avg_price if avg_price > 0 else (
                cum_quote / executed_qty if executed_qty > 0 else 0.0
            )
            
            if entry_price > 0:
                print(f"Entry price received: {entry_price}")
                break
                
            print(f"Waiting for order execution... Attempt {i+1}")
            await asyncio.sleep(1)
            
        await self.exchange_client_factory.close(client)
        
        if entry_price == 0.0:
            raise Exception("Failed to get entry_price after 5 attempts")
        return entry_price

    async def _record_deal(
        self,
        user_id: UUID,
        bot_id: UUID,
        template,
        entry_price: float,
        order_result: dict,
        intent: OrderIntent,
        size: float,
        session,
        strategy=None
    ):
        """Records the trade in the database."""
        print("Saving deal to database")

        side = intent.side

        stop_loss_price = None
        if strategy and hasattr(strategy, 'calculate_stop_loss_price'):
            strategy_side = 'long' if side == 'BUY' else 'short'
            stop_loss_price = strategy.calculate_stop_loss_price(entry_price, strategy_side, intent.symbol)
            if stop_loss_price is not None:
                print(f"Stop-loss calculated by strategy: {stop_loss_price:.4f}")
            else:
                print("⚠️ Stop-loss not calculated by strategy.")

        deal_data = DealCreate(
            user_id=user_id,
            bot_id=bot_id,
            template_id=template.id,
            order_id=str(order_result["orderId"]),
            symbol=intent.symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            status="open",
            stop_loss=float(stop_loss_price) if stop_loss_price is not None else None
        )

        print(f"Data for recording deal: {deal_data}")
        deal = await self.deal_service.create(deal_data, session, autocommit=False)
        print(f"Deal recorded in database, id={deal.id}")

        if stop_loss_price is not None:
            try:
                keys = await self.apikeys_service.get_decrypted_by_user(user_id)
                keys = keys[0] if keys else None
                if keys:
                    print(f"🔑 API keys found for user {user_id}.")
                    client = await self.exchange_client_factory.create(
                        keys.api_key_encrypted, keys.api_secret_encrypted, exchange="binance"
                    )
                    try:
                        quantity = deal.size
                        print(f"📐 Attempting to create stop-loss order: symbol={intent.symbol}, side={'SELL' if intent.side == 'BUY' else 'BUY'}, quantity={quantity}, stop_price={stop_loss_price:.4f}")
                        stop_loss_order_id = await self.deal_service.create_stop_loss_order(
                            deal, session, client, stop_loss_price
                        )
                        print(f"✅ Stop-loss order created on Binance: {stop_loss_order_id}")
                    finally:
                        await self.exchange_client_factory.close(client)
                else:
                    print("❌ Failed to get API keys for stop-loss order creation")
            except Exception as e:
                print(f"❌ Error creating stop-loss order: {e}")
        
        await self.log_service.add_log(
            StrategyLogCreate(
                user_id=user_id,
                deal_id=deal.id,
                strategy=str(getattr(template, 'strategy_name', 'Unknown')),
                signal='long' if side == 'BUY' else 'short',
                comment=f"Deal opened via Binance, order: {order_result.get('orderId')}"
            ),
            session=session,
            autocommit=False
        )
        print(f"Log for deal {deal.id} added")
