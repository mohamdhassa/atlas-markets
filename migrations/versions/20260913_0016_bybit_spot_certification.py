"""Persist Bybit Spot execution certification.

Revision ID: 20260913_0016
Revises: 20260828_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20260913_0016"
down_revision = "20260828_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("broker_profiles", sa.Column("execution_certified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("broker_profiles", sa.Column("execution_certified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("broker_profiles", sa.Column("execution_certification_buy_passed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("broker_profiles", sa.Column("execution_certification_sell_passed", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("broker_profiles", "execution_certification_sell_passed")
    op.drop_column("broker_profiles", "execution_certification_buy_passed")
    op.drop_column("broker_profiles", "execution_certified_at")
    op.drop_column("broker_profiles", "execution_certified")
