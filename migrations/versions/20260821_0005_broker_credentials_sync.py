"""Add encrypted broker credentials and account sync fields.

Revision ID: 20260821_0005
Revises: 20260821_0004
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0005"
down_revision: Union[str, Sequence[str], None] = "20260821_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("broker_profiles", sa.Column("api_key_encrypted", sa.Text(), nullable=True))
    op.add_column("broker_profiles", sa.Column("api_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("broker_profiles", sa.Column("credentials_configured", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("broker_profiles", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("broker_profiles", sa.Column("equity_usd", sa.Float(), nullable=True))
    op.add_column("broker_profiles", sa.Column("wallet_balance_usd", sa.Float(), nullable=True))
    op.add_column("broker_profiles", sa.Column("available_balance_usd", sa.Float(), nullable=True))
    op.add_column("broker_profiles", sa.Column("open_positions_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("broker_profiles", sa.Column("open_orders_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    for column in ["open_orders_count", "open_positions_count", "available_balance_usd", "wallet_balance_usd", "equity_usd", "last_sync_at", "credentials_configured", "api_secret_encrypted", "api_key_encrypted"]:
        op.drop_column("broker_profiles", column)
