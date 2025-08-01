from pydantic import BaseModel, Field


class NovichokParameters(BaseModel):
    ema_fast: int = Field(
        ...,
        ge=2,
        le=100,
        description="Период быстрой EMA"
    )
    ema_slow: int = Field(
        ...,
        ge=3,
        le=300,
        description="Период медленной EMA"
    )
    trend_threshold: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Порог фильтра тренда (доля, например, 0.002 = 0.2%)"
    )
    risk_pct: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Доля депозита на сделку (например, 0.05 = 5%)"
    )
    stop_loss_pct: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Стоп-лосс (доля, например, 0.009 = 0.9%)"
    )

    model_config = {
        "extra": "forbid"
    }
