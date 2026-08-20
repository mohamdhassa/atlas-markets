"""Add broker profiles.

Revision ID: 20260821_0003
Revises: 20260820_0002
Create Date: 2026-08-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0003"
down_revision: Union[str, Sequence[str], None] = "20260820_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("account_label", sa.String(length=96), nullable=False),
        sa.Column("environment", sa.String(length=24), nullable=False),
        sa.Column("external_account_ref", sa.String(length=128), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_connection_status", sa.String(length=24), nullable=False),
        sa.Column("last_connection_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broker_profiles_user_id", "broker_profiles", ["user_id"], unique=False)
    op.create_index("ix_broker_profiles_user_enabled", "broker_profiles", ["user_id", "is_enabled"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_broker_profiles_user_enabled", table_name="broker_profiles")
    op.drop_index("ix_broker_profiles_user_id", table_name="broker_profiles")
    op.drop_table("broker_profiles")
