"""symbol strategy overrides
Revision ID: 20260823_0014
Revises: 20260821_0013
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260823_0014';down_revision='20260821_0013';branch_labels=None;depends_on=None

def upgrade():
    op.create_table('symbol_strategies',
      sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
      sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
      sa.Column('profile_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('broker_profiles.id',ondelete='CASCADE'),nullable=False),
      sa.Column('market',sa.String(16),nullable=False,server_default='CRYPTO'),sa.Column('symbol',sa.String(32),nullable=False),
      sa.Column('mode',sa.String(16),nullable=False,server_default='WATCH'),sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column('timeframe',sa.String(16)),sa.Column('minimum_signal_strength',sa.Float()),sa.Column('risk_per_trade_pct',sa.Float()),sa.Column('stop_atr_multiplier',sa.Float()),sa.Column('take_profit_rr',sa.Float()),sa.Column('max_position_notional_pct',sa.Float()),
      sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint('user_id','profile_id','market','symbol',name='uq_symbol_strategy_scope'))
    op.create_index('ix_symbol_strategies_user_id','symbol_strategies',['user_id']);op.create_index('ix_symbol_strategies_profile_id','symbol_strategies',['profile_id'])

def downgrade():op.drop_table('symbol_strategies')
