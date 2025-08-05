import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, String, DateTime, UUID

from models.base import Base

class UserBot(Base):
    __tablename__ = "user_bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True
    )
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_strategy_templates.id"),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String,
        default="inactive",
        nullable=False
    )
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    celery_task_id: Mapped[str] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="bots")
    template: Mapped["UserStrategyTemplate"] = relationship(
        "UserStrategyTemplate"
    )
    deals = relationship("Deal", back_populates="bot")
