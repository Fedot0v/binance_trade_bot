from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import (
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Integer,
    JSON,
    UUID
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from models.base import Base
from models.user_model import User


class APIKeys(Base):
    __tablename__ = 'api_keys'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    api_key_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    api_secret_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True
    )
    user: Mapped["User"] = relationship("User")


class Deal(Base):
    __tablename__ = 'deals'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=True)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[str] = mapped_column(String, nullable=True)
    stop_loss_order_id: Mapped[str] = mapped_column(String, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    logs: Mapped[list["StrategyLog"]] = relationship(
        "StrategyLog",
        back_populates="deal"
    )
    max_price: Mapped[float] = mapped_column(Float, nullable=True)
    min_price: Mapped[float] = mapped_column(Float, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True
    )
    bot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_bots.id"),
        nullable=False
    )
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_strategy_templates.id"),
        nullable=False
    )
    
    user: Mapped["User"] = relationship("User")
    bot: Mapped["UserBot"] = relationship("UserBot")
    template: Mapped["UserStrategyTemplate"] = relationship(
        "UserStrategyTemplate"
    )


class StrategyLog(Base):
    __tablename__ = 'strategy_logs'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    strategy: Mapped[str] = mapped_column(String, nullable=False)
    signal: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str] = mapped_column(Text)
    deal_id: Mapped[int] = mapped_column(ForeignKey('deals.id'), nullable=True)
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    deal: Mapped["Deal"] = relationship("Deal", back_populates="logs")
    user = relationship("User", back_populates="strategy_logs")


class StrategyConfig(Base):
    __tablename__ = 'strategy_config'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
