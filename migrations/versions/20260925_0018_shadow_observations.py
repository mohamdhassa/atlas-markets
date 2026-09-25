"""Persist v81 forward shadow-strategy observations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260925_0018"
down_revision = "20260913_0017"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "shadow_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("broker_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("symbol_strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False), sa.Column("market", sa.String(16), nullable=False), sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False), sa.Column("action", sa.String(8), nullable=False), sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("regime", sa.String(32), nullable=False), sa.Column("confirmations", sa.Integer(), nullable=False, server_default="0"), sa.Column("contradictions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entry_price", sa.Float(), nullable=False), sa.Column("source_timestamp_ms", sa.BigInteger(), nullable=False), sa.Column("horizon_bars", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("evaluation_due_at", sa.DateTime(timezone=True), nullable=False), sa.Column("news_score", sa.Float(), nullable=True), sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("gross_return_pct", sa.Float(), nullable=True), sa.Column("net_return_pct", sa.Float(), nullable=True), sa.Column("outcome", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True), sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("strategy_id", "source_timestamp_ms", name="uq_shadow_strategy_source_bar"),
    )
    for c in ("user_id","broker_profile_id","strategy_id","provider","market","symbol","action","source_timestamp_ms","evaluation_due_at","outcome","settled_at","created_at"):
        op.create_index(f"ix_shadow_observations_{c}", "shadow_observations", [c])

def downgrade():
    for c in reversed(("user_id","broker_profile_id","strategy_id","provider","market","symbol","action","source_timestamp_ms","evaluation_due_at","outcome","settled_at","created_at")):
        op.drop_index(f"ix_shadow_observations_{c}", table_name="shadow_observations")
    op.drop_table("shadow_observations")
