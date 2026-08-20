"""Phase 2 infrastructure baseline.

Revision ID: 20260820_0001
Revises:
Create Date: 2026-08-20
"""

from typing import Sequence, Union

revision: str = "20260820_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline migration; schema tables arrive in later domain phases."""


def downgrade() -> None:
    """Nothing to remove for the baseline migration."""
