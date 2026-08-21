"""broker account control
Revision ID: 20260821_0012
Revises: 20260821_0011
"""
from alembic import op
import sqlalchemy as sa
revision="20260821_0012"
down_revision="20260821_0011"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("broker_profiles",sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column("broker_profiles",sa.Column("live_execution_enabled",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column("broker_profiles",sa.Column("live_execution_armed_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("broker_profiles",sa.Column("credential_blob_encrypted",sa.Text(),nullable=True))

def downgrade():
    op.drop_column("broker_profiles","credential_blob_encrypted")
    op.drop_column("broker_profiles","live_execution_armed_at")
    op.drop_column("broker_profiles","live_execution_enabled")
    op.drop_column("broker_profiles","is_active")
