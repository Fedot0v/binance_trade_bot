from pydantic import BaseModel, Field


class CompensationParameters(BaseModel):
    ema_fast: int = Field(
        default=10,
        ge=2,
        le=100,
        description="Период быстрой EMA для BTC"
    )
    ema_slow: int = Field(
        default=30,
        ge=3,
        le=300,
        description="Период медленной EMA для BTC"
    )
    trend_threshold: float = Field(
        default=0.001,
        gt=0,
        lt=1,
        description="Порог фильтра тренда для BTC (доля, например, 0.001 = 0.1%)"
    )
    btc_deposit_prct: float = Field(
        default=0.05,
        gt=0,
        lt=1,
        description="Доля депозита на сделку BTC (например, 0.05 = 5%)"
    )
    btc_stop_loss_pct: float = Field(
        default=0.012,
        gt=0,
        lt=1,
        description="Стоп-лосс BTC (доля, например, 0.012 = 1.2%)"
    )

    eth_deposit_prct: float = Field(
        default=0.1,
        gt=0,
        lt=1,
        description="Доля депозита на сделку ETH (например, 0.1 = 10%)"
    )
    eth_stop_loss_pct: float = Field(
        default=0.01,
        gt=0,
        lt=1,
        description="Стоп-лосс ETH (доля, например, 0.01 = 1.0%)"
    )
    
    # Параметры компенсации
    compensation_threshold: float = Field(
        default=0.0025,
        gt=0,
        lt=1,
        description="Порог для запуска компенсации (доля, например, 0.0025 = 0.25%)"
    )
    compensation_time_window: int = Field(
        default=15,
        ge=1,
        le=60,
        description="Временное окно для компенсации в минутах"
    )
    impulse_threshold: float = Field(
        default=0.004,
        gt=0,
        lt=1,
        description="Порог импульса для компенсации (доля, например, 0.004 = 0.4%)"
    )
    candles_against_threshold: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Количество свечей против позиции для компенсации"
    )
    max_trade_duration: int = Field(
        default=60,
        ge=10,
        le=240,
        description="Максимальная продолжительность сделки в минутах"
    )

    model_config = {
        "extra": "forbid"
    }
