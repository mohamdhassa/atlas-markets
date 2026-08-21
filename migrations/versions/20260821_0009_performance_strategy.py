"""performance analytics and strategy profile
Revision ID: 20260821_0009
Revises: 20260821_0008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20260821_0009"
down_revision="20260821_0008"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("strategy_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("timeframe", sa.String(16), nullable=False, server_default="5m"),
        sa.Column("minimum_signal_strength", sa.Float(), nullable=False, server_default="65"),
        sa.Column("stop_atr_multiplier", sa.Float(), nullable=False, server_default="1.5"),
        sa.Column("take_profit_rr", sa.Float(), nullable=False, server_default="2"),
        sa.Column("max_position_notional_pct", sa.Float(), nullable=False, server_default="20"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("strategy_profiles")
