from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260930_0021"
down_revision = "20260930_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("broker_profiles", sa.Column("live_execution_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("broker_profiles", sa.Column("live_execution_last_disarm_reason", sa.String(length=500), nullable=True))
    op.create_table(
        "live_execution_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("armed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["broker_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_execution_events_profile_id", "live_execution_events", ["profile_id"])
    op.create_index("ix_live_execution_events_owner_user_id", "live_execution_events", ["owner_user_id"])
    op.create_index("ix_live_execution_events_actor_user_id", "live_execution_events", ["actor_user_id"])
    op.create_index("ix_live_execution_events_created_at", "live_execution_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_live_execution_events_created_at", table_name="live_execution_events")
    op.drop_index("ix_live_execution_events_actor_user_id", table_name="live_execution_events")
    op.drop_index("ix_live_execution_events_owner_user_id", table_name="live_execution_events")
    op.drop_index("ix_live_execution_events_profile_id", table_name="live_execution_events")
    op.drop_table("live_execution_events")
    op.drop_column("broker_profiles", "live_execution_last_disarm_reason")
    op.drop_column("broker_profiles", "live_execution_expires_at")
