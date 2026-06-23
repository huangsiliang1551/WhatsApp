"""add template send log analytics snapshot fields

Revision ID: 20260607_0006
Revises: 20260607_0005
Create Date: 2026-06-07 22:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260607_0006"
down_revision: str | None = "20260607_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("template_send_logs", sa.Column("waba_id", sa.String(length=128), nullable=True))
    op.add_column("template_send_logs", sa.Column("template_name", sa.String(length=100), nullable=True))
    op.add_column("template_send_logs", sa.Column("template_language", sa.String(length=16), nullable=True))
    op.add_column("template_send_logs", sa.Column("template_category", sa.String(length=32), nullable=True))
    op.add_column("template_send_logs", sa.Column("template_code", sa.String(length=255), nullable=True))
    op.add_column("template_send_logs", sa.Column("delivered_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("template_send_logs", sa.Column("read_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("template_send_logs", sa.Column("failed_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("template_send_logs", sa.Column("last_status_at", sa.DateTime(timezone=False), nullable=True))
    op.create_index("ix_template_send_logs_waba_id", "template_send_logs", ["waba_id"])


def downgrade() -> None:
    op.drop_index("ix_template_send_logs_waba_id", table_name="template_send_logs")
    op.drop_column("template_send_logs", "last_status_at")
    op.drop_column("template_send_logs", "failed_at")
    op.drop_column("template_send_logs", "read_at")
    op.drop_column("template_send_logs", "delivered_at")
    op.drop_column("template_send_logs", "template_code")
    op.drop_column("template_send_logs", "template_category")
    op.drop_column("template_send_logs", "template_language")
    op.drop_column("template_send_logs", "template_name")
    op.drop_column("template_send_logs", "waba_id")
