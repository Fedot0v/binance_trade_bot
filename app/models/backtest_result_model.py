from datetime import datetime
import uuid

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Text,
    Integer,
    JSON,
    UUID as SQLAUUID
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from models.base import Base
from models.user_model import User

class BacktestResultModel(Base):
    __tablename__ = 'backtest_results'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        SQLAUUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
        nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    results: Mapped[dict] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship("User")
