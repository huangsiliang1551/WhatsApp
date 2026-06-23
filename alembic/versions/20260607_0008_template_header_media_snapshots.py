"""add template header media snapshot fields

Revision ID: 20260607_0008
Revises: 20260607_0007
Create Date: 2026-06-08 00:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260607_0008"
down_revision: str | None = "20260607_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "template_send_logs",
        sa.Column("header_media_asset_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "template_send_logs",
        sa.Column("header_media_asset_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "template_send_logs",
        sa.Column("header_media_asset_type", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_template_send_logs_header_media_asset_id",
        "template_send_logs",
        ["header_media_asset_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_send_logs_header_media_asset_id", table_name="template_send_logs")
    op.drop_column("template_send_logs", "header_media_asset_type")
    op.drop_column("template_send_logs", "header_media_asset_name")
    op.drop_column("template_send_logs", "header_media_asset_id")
