from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, ForeignKey, func

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)


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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped["User"] = relationship("User")