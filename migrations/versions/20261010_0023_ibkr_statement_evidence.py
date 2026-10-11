"""Durable reviewed statement evidence independent of protection audit updates."""
from alembic import op
import sqlalchemy as sa

revision = '20261010_0023'
down_revision = '20261001_0022'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ibkr_statement_evidence',
        sa.Column('action_id', sa.Uuid(), sa.ForeignKey('automation_actions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('broker_profile_id', sa.Uuid(), sa.ForeignKey('broker_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operator_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('evidence_json', sa.Text(), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_ibkr_statement_evidence_broker_profile_id', 'ibkr_statement_evidence', ['broker_profile_id'])
    op.create_index('ix_ibkr_statement_evidence_user_id', 'ibkr_statement_evidence', ['user_id'])


def downgrade():
    op.drop_index('ix_ibkr_statement_evidence_user_id', table_name='ibkr_statement_evidence')
    op.drop_index('ix_ibkr_statement_evidence_broker_profile_id', table_name='ibkr_statement_evidence')
    op.drop_table('ibkr_statement_evidence')
