"""Add provider-aware shadow scan audit and excursion analytics."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260925_0019"
down_revision = "20260925_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shadow_observations", sa.Column("max_favorable_excursion_pct", sa.Float(), nullable=True))
    op.add_column("shadow_observations", sa.Column("max_adverse_excursion_pct", sa.Float(), nullable=True))
    op.add_column("shadow_observations", sa.Column("round_trip_cost_bps", sa.Float(), nullable=False, server_default="8"))
    op.create_table(
        "shadow_scan_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("broker_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("symbol_strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("user_id", "broker_profile_id", "strategy_id", "provider", "market", "symbol", "status", "reason", "created_at"):
        op.create_index(f"ix_shadow_scan_events_{column}", "shadow_scan_events", [column])


def downgrade():
    for column in reversed(("user_id", "broker_profile_id", "strategy_id", "provider", "market", "symbol", "status", "reason", "created_at")):
        op.drop_index(f"ix_shadow_scan_events_{column}", table_name="shadow_scan_events")
    op.drop_table("shadow_scan_events")
    op.drop_column("shadow_observations", "round_trip_cost_bps")
    op.drop_column("shadow_observations", "max_adverse_excursion_pct")
    op.drop_column("shadow_observations", "max_favorable_excursion_pct")
