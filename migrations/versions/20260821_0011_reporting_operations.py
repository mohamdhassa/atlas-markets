"""daily reporting operations
Revision ID: 20260821_0011
Revises: 20260821_0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20260821_0011"
down_revision="20260821_0010"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("daily_account_reports",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("profile_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("broker_profiles.id",ondelete="CASCADE"),nullable=False),
        sa.Column("report_date",sa.Date(),nullable=False),
        sa.Column("starting_equity",sa.Float(),nullable=False,server_default="0"),
        sa.Column("ending_equity",sa.Float(),nullable=False,server_default="0"),
        sa.Column("realized_pnl",sa.Float(),nullable=False,server_default="0"),
        sa.Column("closed_trades",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("wins",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("losses",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("signals_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("approved_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("generated_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id","report_date",name="uq_daily_account_report"))
    op.create_index("ix_daily_account_reports_profile_id","daily_account_reports",["profile_id"])
    op.create_index("ix_daily_account_reports_report_date","daily_account_reports",["report_date"])

def downgrade():
    op.drop_table("daily_account_reports")
