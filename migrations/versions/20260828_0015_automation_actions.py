"""Phase 34 persistent automation action ledger.

Revision ID: 20260828_0015
Revises: 20260823_0014
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260828_0015'
down_revision = '20260823_0014'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'automation_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('automation_scans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('broker_profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('environment', sa.String(length=24), nullable=True),
        sa.Column('market', sa.String(length=24), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=True),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('reason', sa.String(length=128), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('sizing_policy', sa.String(length=64), nullable=True),
        sa.Column('broker_order_id', sa.String(length=128), nullable=True),
        sa.Column('broker_position_id', sa.String(length=128), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_automation_actions_scan_id', 'automation_actions', ['scan_id'])
    op.create_index('ix_automation_actions_user_id', 'automation_actions', ['user_id'])
    op.create_index('ix_automation_actions_created_at', 'automation_actions', ['created_at'])
    op.create_index('ix_automation_actions_symbol', 'automation_actions', ['symbol'])
    op.create_index('ix_automation_actions_status', 'automation_actions', ['status'])


def downgrade():
    op.drop_table('automation_actions')
