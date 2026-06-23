"""add template send log status dimensions

Revision ID: 20260607_0010
Revises: 20260607_0009
Create Date: 2026-06-08 09:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260607_0010"
down_revision: str | None = "20260607_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "template_send_logs",
        sa.Column("conversation_origin_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "template_send_logs",
        sa.Column("conversation_category", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "template_send_logs",
        sa.Column("pricing_model", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "template_send_logs",
        sa.Column("billable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_template_send_logs_conversation_origin_type",
        "template_send_logs",
        ["conversation_origin_type"],
    )
    op.create_index(
        "ix_template_send_logs_conversation_category",
        "template_send_logs",
        ["conversation_category"],
    )
    op.create_index(
        "ix_template_send_logs_pricing_model",
        "template_send_logs",
        ["pricing_model"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_send_logs_pricing_model", table_name="template_send_logs")
    op.drop_index("ix_template_send_logs_conversation_category", table_name="template_send_logs")
    op.drop_index("ix_template_send_logs_conversation_origin_type", table_name="template_send_logs")
    op.drop_column("template_send_logs", "billable")
    op.drop_column("template_send_logs", "pricing_model")
    op.drop_column("template_send_logs", "conversation_category")
    op.drop_column("template_send_logs", "conversation_origin_type")
