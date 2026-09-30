from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260930_0020"
down_revision = "20260925_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbol_strategy_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("restored_from_revision", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["broker_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "revision_number", name="uq_symbol_strategy_revision_number"),
    )
    op.create_index("ix_symbol_strategy_revisions_strategy_id", "symbol_strategy_revisions", ["strategy_id"])
    op.create_index("ix_symbol_strategy_revisions_user_id", "symbol_strategy_revisions", ["user_id"])
    op.create_index("ix_symbol_strategy_revisions_actor_user_id", "symbol_strategy_revisions", ["actor_user_id"])
    op.create_index("ix_symbol_strategy_revisions_profile_id", "symbol_strategy_revisions", ["profile_id"])
    op.create_index("ix_symbol_strategy_revisions_created_at", "symbol_strategy_revisions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_symbol_strategy_revisions_created_at", table_name="symbol_strategy_revisions")
    op.drop_index("ix_symbol_strategy_revisions_profile_id", table_name="symbol_strategy_revisions")
    op.drop_index("ix_symbol_strategy_revisions_actor_user_id", table_name="symbol_strategy_revisions")
    op.drop_index("ix_symbol_strategy_revisions_user_id", table_name="symbol_strategy_revisions")
    op.drop_index("ix_symbol_strategy_revisions_strategy_id", table_name="symbol_strategy_revisions")
    op.drop_table("symbol_strategy_revisions")
