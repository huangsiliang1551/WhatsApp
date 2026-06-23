"""add template lifecycle fields

Revision ID: 20260607_0004
Revises: 20260607_0003
Create Date: 2026-06-07 03:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260607_0004"
down_revision: str | None = "20260607_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("message_templates", sa.Column("submitted_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("message_templates", sa.Column("last_synced_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("message_templates", sa.Column("provider_template_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("message_templates", "provider_template_payload")
    op.drop_column("message_templates", "last_synced_at")
    op.drop_column("message_templates", "submitted_at")
