"""paper execution lifecycle
Revision ID: 20260821_0007
Revises: 20260821_0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20260821_0007"
down_revision="20260821_0006"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("paper_positions", sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_paper_positions_signal", "paper_positions", "signals", ["signal_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_paper_positions_signal_id", "paper_positions", ["signal_id"])
    op.add_column("paper_orders", sa.Column("order_type", sa.String(16), nullable=False, server_default="MARKET"))
    op.add_column("paper_orders", sa.Column("exit_reason", sa.String(32), nullable=True))
    op.add_column("paper_orders", sa.Column("realized_pnl", sa.Float(), nullable=True))

def downgrade():
    op.drop_column("paper_orders", "realized_pnl"); op.drop_column("paper_orders", "exit_reason"); op.drop_column("paper_orders", "order_type")
    op.drop_index("ix_paper_positions_signal_id", table_name="paper_positions")
    op.drop_constraint("fk_paper_positions_signal", "paper_positions", type_="foreignkey")
    op.drop_column("paper_positions", "signal_id")
