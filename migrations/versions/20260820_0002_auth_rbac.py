"""Add authentication and RBAC tables.

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0002"
down_revision: Union[str, Sequence[str], None] = "20260820_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('ADMIN', 'USER')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)

    op.create_table(
        "auth_audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_audit_log_user_id", "auth_audit_log", ["user_id"], unique=False)
    op.create_index("ix_auth_audit_log_created_at", "auth_audit_log", ["created_at"], unique=False)
    op.create_index("ix_auth_audit_log_action", "auth_audit_log", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_audit_log_action", table_name="auth_audit_log")
    op.drop_index("ix_auth_audit_log_created_at", table_name="auth_audit_log")
    op.drop_index("ix_auth_audit_log_user_id", table_name="auth_audit_log")
    op.drop_table("auth_audit_log")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_token_hash", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
