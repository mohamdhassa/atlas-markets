"""Track ATLAS-owned Bybit Spot inventory.

Revision ID: 20260913_0017
Revises: 20260913_0016
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260913_0017"
down_revision = "20260913_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bybit_managed_inventory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("broker_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("managed_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("average_entry_price", sa.Float(), nullable=True),
        sa.Column("cumulative_bought_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cumulative_sold_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("broker_profile_id", "symbol", name="uq_bybit_managed_inventory_profile_symbol"),
    )
    op.create_index("ix_bybit_managed_inventory_user_id", "bybit_managed_inventory", ["user_id"])
    op.create_index("ix_bybit_managed_inventory_broker_profile_id", "bybit_managed_inventory", ["broker_profile_id"])
    op.create_index("ix_bybit_managed_inventory_symbol", "bybit_managed_inventory", ["symbol"])


def downgrade():
    op.drop_index("ix_bybit_managed_inventory_symbol", table_name="bybit_managed_inventory")
    op.drop_index("ix_bybit_managed_inventory_broker_profile_id", table_name="bybit_managed_inventory")
    op.drop_index("ix_bybit_managed_inventory_user_id", table_name="bybit_managed_inventory")
    op.drop_table("bybit_managed_inventory")
