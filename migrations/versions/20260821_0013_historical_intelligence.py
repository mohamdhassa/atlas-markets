"""historical intelligence
Revision ID: 20260821_0013
Revises: 20260821_0012
"""
from alembic import op
import sqlalchemy as sa
revision="20260821_0013"
down_revision="20260821_0012"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("historical_candles",
        sa.Column("id",sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column("market",sa.String(16),nullable=False),sa.Column("symbol",sa.String(32),nullable=False),sa.Column("interval",sa.String(16),nullable=False),
        sa.Column("timestamp_ms",sa.BigInteger(),nullable=False),sa.Column("open",sa.Float(),nullable=False),sa.Column("high",sa.Float(),nullable=False),sa.Column("low",sa.Float(),nullable=False),sa.Column("close",sa.Float(),nullable=False),sa.Column("volume",sa.Float(),nullable=False,server_default="0"),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.UniqueConstraint("market","symbol","interval","timestamp_ms",name="uq_historical_candle"))
    op.create_index("ix_historical_lookup","historical_candles",["market","symbol","interval","timestamp_ms"])
    op.create_table("historical_backtest_runs",
        sa.Column("id",sa.Integer(),primary_key=True,autoincrement=True),sa.Column("market",sa.String(16),nullable=False),sa.Column("symbol",sa.String(32),nullable=False),sa.Column("interval",sa.String(16),nullable=False),
        sa.Column("sample_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("signals",sa.Integer(),nullable=False,server_default="0"),sa.Column("wins",sa.Integer(),nullable=False,server_default="0"),sa.Column("losses",sa.Integer(),nullable=False,server_default="0"),sa.Column("win_rate",sa.Float(),nullable=False,server_default="0"),sa.Column("avg_return_pct",sa.Float(),nullable=False,server_default="0"),sa.Column("max_drawdown_pct",sa.Float(),nullable=False,server_default="0"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))

def downgrade():
    op.drop_table("historical_backtest_runs");op.drop_index("ix_historical_lookup",table_name="historical_candles");op.drop_table("historical_candles")
