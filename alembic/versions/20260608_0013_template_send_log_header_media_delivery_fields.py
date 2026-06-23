"""add template send log header media delivery fields

Revision ID: 20260608_0013
Revises: 20260608_0012
Create Date: 2026-06-08 14:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260608_0013"
down_revision: str | None = "20260608_0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.add_column(sa.Column("header_media_meta_media_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("header_media_sync_status", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.drop_column("header_media_sync_status")
        batch_op.drop_column("header_media_meta_media_id")
