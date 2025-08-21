"""add_stop_loss_order_id_to_deals

Revision ID: 34c60f26c8e7
Revises: 
Create Date: 2025-08-21 12:50:26.958379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34c60f26c8e7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add stop_loss_order_id and order_id columns to deals table."""
    # Добавляем поле order_id (если его нет)
    try:
        op.add_column('deals', sa.Column('order_id', sa.String(), nullable=True))
        op.execute("COMMENT ON COLUMN deals.order_id IS 'ID основного ордера на Binance'")
    except Exception:
        # Поле уже существует, пропускаем
        pass
    
    # Добавляем поле stop_loss_order_id
    op.add_column('deals', sa.Column('stop_loss_order_id', sa.String(), nullable=True))
    
    # Добавляем комментарий к полю
    op.execute("COMMENT ON COLUMN deals.stop_loss_order_id IS 'ID стоп-лосс ордера на Binance'")


def downgrade() -> None:
    """Remove stop_loss_order_id and order_id columns from deals table."""
    # Удаляем поле stop_loss_order_id
    op.drop_column('deals', 'stop_loss_order_id')
    
    # Удаляем поле order_id (если оно было добавлено этой миграцией)
    try:
        op.drop_column('deals', 'order_id')
    except Exception:
        # Поле не существует, пропускаем
        pass
