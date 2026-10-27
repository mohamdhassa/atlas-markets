"""Durable administrator-approved Paper onboarding queue."""
from alembic import op
import sqlalchemy as sa
revision='20261027_0024'
down_revision='20261010_0023'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('ibkr_onboarding',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False,unique=True),
        sa.Column('account_id',sa.String(40),nullable=False),
        sa.Column('account_label',sa.String(96),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('approved_by',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('profile_id',sa.Uuid(),sa.ForeignKey('broker_profiles.id',ondelete='SET NULL'),nullable=True),
        sa.Column('credentials_encrypted',sa.Text(),nullable=True),
        sa.Column('bridge_token_encrypted',sa.Text(),nullable=True),
        sa.Column('lease_hash',sa.String(64),nullable=True),
        sa.Column('lease_until',sa.DateTime(timezone=True),nullable=True),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('error_code',sa.String(48),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_ibkr_onboarding_approved_by','ibkr_onboarding',['approved_by'])
    op.create_index('ix_ibkr_onboarding_profile_id','ibkr_onboarding',['profile_id'])
    op.create_index('ix_ibkr_onboarding_account_id','ibkr_onboarding',['account_id'])
    op.create_index('ix_ibkr_onboarding_status','ibkr_onboarding',['status'])


def downgrade():
    op.drop_index('ix_ibkr_onboarding_approved_by',table_name='ibkr_onboarding')
    op.drop_index('ix_ibkr_onboarding_profile_id',table_name='ibkr_onboarding')
    op.drop_index('ix_ibkr_onboarding_account_id',table_name='ibkr_onboarding')
    op.drop_index('ix_ibkr_onboarding_status',table_name='ibkr_onboarding')
    op.drop_table('ibkr_onboarding')
