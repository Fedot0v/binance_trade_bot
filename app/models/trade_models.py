from datetime import datetime
from typing import Any

from sqlalchemy import (
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Integer,
    JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class UserSettings(Base):
    __tablename__ = 'user_settings'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    deposit: Mapped[float] = mapped_column(Float, nullable=False)
    leverage: Mapped[float] = mapped_column(Float, nullable=False)
    entry_pct: Mapped[float] = mapped_column(Float, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now()
    )


class APIKeys(Base):
    __tablename__ = 'api_keys'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    api_key_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    api_secret_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Deal(Base):
    __tablename__ = 'deals'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closed_at: Mapped[datetime] = mapped_column(DateTime)
    logs: Mapped[list["StrategyLog"]] = relationship(
        "StrategyLog",
        back_populates="deal"
    )


class StrategyLog(Base):
    __tablename__ = 'strategy_logs'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    strategy: Mapped[str] = mapped_column(String, nullable=False)
    signal: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str] = mapped_column(Text)
    deal_id: Mapped[int] = mapped_column(ForeignKey('deals.id'))
    deal: Mapped["Deal"] = relationship("Deal", back_populates="logs")


class MarketData(Base):
    __tablename__ = 'market_data'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)


class StrategyConfig(Base):
    __tablename__ = 'strategy_config'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
