"""add_stop_loss_pct_to_novichok_strategy

Revision ID: 80c36321a8e6
Revises: 34c60f26c8e7
Create Date: 2025-08-21 13:36:49.422913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '80c36321a8e6'
down_revision: Union[str, Sequence[str], None] = '34c60f26c8e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляем параметр stop_loss_pct в существующие стратегии Novichok."""
    
    # Обновляем существующие конфигурации стратегий Novichok
    op.execute("""
        UPDATE strategy_config 
        SET parameters = parameters || '{"stop_loss_pct": 0.02}'::jsonb
        WHERE name = 'NovichokStrategy' 
        AND NOT (parameters ? 'stop_loss_pct')
    """)
    
    # Обновляем существующие шаблоны пользователей для стратегии Novichok
    op.execute("""
        UPDATE user_strategy_templates 
        SET parameters = parameters || '{"stop_loss_pct": 0.02}'::jsonb
        WHERE strategy_config_id IN (
            SELECT id FROM strategy_config WHERE name = 'NovichokStrategy'
        )
        AND NOT (parameters ? 'stop_loss_pct')
    """)


def downgrade() -> None:
    """Удаляем параметр stop_loss_pct из стратегий Novichok."""
    
    # Удаляем параметр stop_loss_pct из шаблонов пользователей
    op.execute("""
        UPDATE user_strategy_templates 
        SET parameters = parameters - 'stop_loss_pct'
        WHERE strategy_config_id IN (
            SELECT id FROM strategy_config WHERE name = 'NovichokStrategy'
        )
    """)
    
    # Удаляем параметр stop_loss_pct из конфигураций стратегий
    op.execute("""
        UPDATE strategy_config 
        SET parameters = parameters - 'stop_loss_pct'
        WHERE name = 'NovichokStrategy'
    """)
