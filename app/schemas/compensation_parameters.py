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
    compensation_delay_candles: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Количество свечей ожидания после первого сигнала по BTC"
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

    # Новые параметры подтверждения и аварийного входа
    eth_confirmation_candles: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Сколько последних свечей ETH должны идти в сторону BTC"
    )
    require_eth_ema_alignment: bool = Field(
        default=True,
        description="Требовать совпадение тренда ETH по EMA с направлением BTC"
    )
    eth_volume_min_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="Минимальное отношение объёма ETH (последние N к предыдущим). 0 — отключено"
    )
    high_adverse_threshold: float = Field(
        default=0.01,
        gt=0,
        lt=1,
        description="Порог аварийного входа без ожидания ETH (доля, например, 0.01 = 1%)"
    )
    max_compensation_window_candles: int = Field(
        default=30,
        ge=5,
        le=200,
        description="Максимальное число свечей ожидания от первого сигнала BTC"
    )

    # Направление компенсации: по умолчанию противоположно BTC (хедж)
    eth_compensation_opposite: bool = Field(
        default=True,
        description="Если True, ETH открывается в противоположную сторону к BTC; если False — в ту же"
    )

    model_config = {
        "extra": "forbid"
    }
