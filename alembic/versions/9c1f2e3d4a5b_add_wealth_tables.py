"""Add wealth monitor tables

Revision ID: 9c1f2e3d4a5b
Revises: f6b8b3ac0842
Create Date: 2026-11-02 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c1f2e3d4a5b'
down_revision: Union[str, Sequence[str], None] = 'f6b8b3ac0842'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'wealth_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False, server_default='liquidita'),
        sa.Column('active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_wealth_accounts_user_id', 'wealth_accounts', ['user_id'])
    op.create_index('ix_wealth_accounts_active', 'wealth_accounts', ['active'])

    op.create_table(
        'wealth_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('balance', sa.Float(), nullable=False),
        sa.Column('snapshot_date', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['wealth_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'account_id', 'snapshot_date', name='uq_wealth_snapshot_account_date'
        ),
    )
    op.create_index('ix_wealth_snapshots_user_id', 'wealth_snapshots', ['user_id'])
    op.create_index('ix_wealth_snapshots_account_id', 'wealth_snapshots', ['account_id'])
    op.create_index('ix_wealth_snapshots_snapshot_date', 'wealth_snapshots', ['snapshot_date'])


def downgrade() -> None:
    op.drop_index('ix_wealth_snapshots_snapshot_date', table_name='wealth_snapshots')
    op.drop_index('ix_wealth_snapshots_account_id', table_name='wealth_snapshots')
    op.drop_index('ix_wealth_snapshots_user_id', table_name='wealth_snapshots')
    op.drop_table('wealth_snapshots')

    op.drop_index('ix_wealth_accounts_active', table_name='wealth_accounts')
    op.drop_index('ix_wealth_accounts_user_id', table_name='wealth_accounts')
    op.drop_table('wealth_accounts')
