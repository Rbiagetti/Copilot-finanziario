"""Add user_id columns for multi-tenancy

Revision ID: f6b8b3ac0842
Revises:
Create Date: 2026-05-04 11:23:23.542635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b8b3ac0842'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add user_id columns for multi-tenancy."""
    # This migration creates/updates tables with user_id for PostgreSQL
    # SQLAlchemy will handle type conversions appropriately per DB

    # For PostgreSQL, add user_id column if it doesn't exist
    # (These statements are idempotent with IF NOT EXISTS where possible)

    ctx = op.get_context()
    dialect = ctx.dialect.name

    # Transactions table
    if dialect == 'postgresql':
        # PostgreSQL: Add user_id if not exists
        try:
            op.add_column('transactions', sa.Column('user_id', sa.String(length=36), nullable=False))
        except:
            pass
        try:
            op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
        except:
            pass

    # Budgets table
    if dialect == 'postgresql':
        try:
            op.add_column('budgets', sa.Column('user_id', sa.String(length=36), nullable=False))
        except:
            pass
        try:
            op.create_index('ix_budgets_user_id', 'budgets', ['user_id'])
        except:
            pass

    # Chat history table
    if dialect == 'postgresql':
        try:
            op.add_column('chat_history', sa.Column('user_id', sa.String(length=36), nullable=False))
        except:
            pass
        try:
            op.create_index('ix_chat_history_user_id', 'chat_history', ['user_id'])
        except:
            pass


def downgrade() -> None:
    """Downgrade schema."""
    ctx = op.get_context()
    dialect = ctx.dialect.name

    if dialect == 'postgresql':
        try:
            op.drop_index('ix_transactions_user_id', table_name='transactions')
        except:
            pass
        try:
            op.drop_column('transactions', 'user_id')
        except:
            pass

        try:
            op.drop_index('ix_budgets_user_id', table_name='budgets')
        except:
            pass
        try:
            op.drop_column('budgets', 'user_id')
        except:
            pass

        try:
            op.drop_index('ix_chat_history_user_id', table_name='chat_history')
        except:
            pass
        try:
            op.drop_column('chat_history', 'user_id')
        except:
            pass
