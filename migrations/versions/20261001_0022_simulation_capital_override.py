from alembic import op
import sqlalchemy as sa

revision = "20261001_0022"
down_revision = "20260930_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "broker_profiles",
        sa.Column("simulation_capital_override_usd", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("broker_profiles", "simulation_capital_override_usd")
