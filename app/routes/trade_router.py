from fastapi import APIRouter, Depends

from app.services.trade_service import TradeService
from app.dependencies.di_factories import get_trade_service


router = APIRouter(prefix="/trade", tags=["TradeBot"])


@router.post("/start/")
async def start_trading(user_id: int, trade_service: TradeService = Depends(get_trade_service)):
    await trade_service.start_trading(user_id)
    return {"status": "started", "user_id": user_id}


@router.post("/stop/")
async def stop_trading(user_id: int, trade_service: TradeService = Depends(get_trade_service)):
    await trade_service.stop_trading(user_id)
    return {"status": "stopped", "user_id": user_id}


@router.get("/status/")
async def get_bot_status(user_id: int, trade_service: TradeService = Depends(get_trade_service)):
    status = await trade_service.get_bot_status(user_id)
    return {"status": status, "user_id": user_id}
