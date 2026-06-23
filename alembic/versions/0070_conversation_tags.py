"""conversation_tags column

Revision ID: 0070
Revises: 0069
Create Date: 2026-06-12 13:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0070"
down_revision: str | None = "0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("tags", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "tags")
