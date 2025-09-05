from datetime import datetime
import uuid
import enum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, ForeignKey, func, Boolean, DateTime, JSON, UUID, Enum as SQLAEnum
from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from models.base import Base


class Symbols(enum.Enum):
    BTCUSDT = "BTCUSDT"
    ETHUSDT = "ETHUSDT"


class Intervals(enum.Enum):
    min1 = "1m"
    min5 = "5m"
    min15 = "15m"
    hour1 = "1h"
    hour4 = "4h"
    day1 = "1d"


class User(Base, SQLAlchemyBaseUserTableUUID):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(
        unique=True,
        index=True,
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    is_verified: Mapped[bool] = mapped_column(default=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    
    api_keys = relationship(
        "APIKeys",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    deals = relationship(
        "Deal",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    strategy_templates = relationship(
        "UserStrategyTemplate",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    bots = relationship("UserBot", back_populates="user")
    strategy_logs = relationship(
        "StrategyLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class UserStrategyTemplate(Base):
    __tablename__ = 'user_strategy_templates'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    leverage: Mapped[float] = mapped_column(Float, nullable=False)
    strategy_config_id: Mapped[int] = mapped_column(
        ForeignKey('strategy_config.id'),
        index=True
    )
    parameters: Mapped[dict] = mapped_column(JSON, nullable=True)
    symbol: Mapped[str] = mapped_column(SQLAEnum(Symbols), nullable=False)
    interval: Mapped[str] = mapped_column(SQLAEnum(Intervals), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False)
    initial_balance: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="strategy_templates"
    )
    bots = relationship("UserBot", back_populates="template")
    deals = relationship("Deal", back_populates="template")
