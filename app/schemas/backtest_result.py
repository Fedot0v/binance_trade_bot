from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class BacktestResultBase(BaseModel):
    task_id: str = Field(..., description="ID задачи Celery для бэктеста")
    template_id: int = Field(..., description="ID шаблона стратегии")
    user_id: UUID = Field(..., description="ID пользователя")
    status: str = Field("pending", description="Статус выполнения бэктеста")
    results: Optional[Dict[str, Any]] = Field(None, description="JSON-результаты бэктеста")


class BacktestResultCreate(BacktestResultBase):
    pass


class BacktestResultRead(BacktestResultBase):
    id: int = Field(..., description="ID записи в базе данных")
    created_at: datetime = Field(..., description="Дата и время создания записи")
    completed_at: Optional[datetime] = Field(None, description="Дата и время завершения бэктеста")

    class Config:
        from_attributes = True
