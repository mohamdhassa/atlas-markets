"""automation engine state and scan history
Revision ID: 20260821_0008
Revises: 20260821_0007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20260821_0008"
down_revision="20260821_0007"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("automation_state",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("name",sa.String(64),nullable=False,unique=True),
        sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("killed",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("auto_execute_paper",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("interval_seconds",sa.Integer(),nullable=False,server_default="300"),
        sa.Column("symbols_csv",sa.Text(),nullable=False,server_default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT"),
        sa.Column("last_scan_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("next_scan_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_table("automation_scans",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("status",sa.String(24),nullable=False,server_default="RUNNING"),
        sa.Column("symbols_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("accounts_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("signals_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("approved_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("executed_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("error_message",sa.Text(),nullable=True),
        sa.Column("started_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.Column("finished_at",sa.DateTime(timezone=True),nullable=True))
    op.create_index("ix_automation_scans_status","automation_scans",["status"])
    op.create_index("ix_automation_scans_started_at","automation_scans",["started_at"])

def downgrade():
    op.drop_table("automation_scans")
    op.drop_table("automation_state")
