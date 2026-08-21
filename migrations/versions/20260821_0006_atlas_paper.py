"""add ATLAS PAPER wallet, positions and orders

Revision ID: 20260821_0006
Revises: 20260821_0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260821_0006"
down_revision = "20260821_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("paper_wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_profiles.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("starting_balance", sa.Float(), nullable=False, server_default="100000"),
        sa.Column("cash_balance", sa.Float(), nullable=False, server_default="100000"),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_paper_wallets_profile_id", "paper_wallets", ["profile_id"], unique=True)
    op.create_table("paper_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False), sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False), sa.Column("entry_price", sa.Float(), nullable=False), sa.Column("mark_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=True), sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_paper_positions_profile_id", "paper_positions", ["profile_id"])
    op.create_index("ix_paper_positions_symbol", "paper_positions", ["symbol"])
    op.create_table("paper_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False), sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False), sa.Column("fill_price", sa.Float(), nullable=False), sa.Column("notional", sa.Float(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="FILLED"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_paper_orders_profile_id", "paper_orders", ["profile_id"])
    op.create_index("ix_paper_orders_signal_id", "paper_orders", ["signal_id"])
    op.create_index("ix_paper_orders_symbol", "paper_orders", ["symbol"])


def downgrade() -> None:
    op.drop_table("paper_orders")
    op.drop_table("paper_positions")
    op.drop_table("paper_wallets")
