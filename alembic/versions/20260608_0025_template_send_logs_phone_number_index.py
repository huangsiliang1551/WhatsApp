"""index template send logs phone number scope

Revision ID: 20260608_0025
Revises: 20260608_0024
Create Date: 2026-06-08 22:00:00
"""

from __future__ import annotations

from alembic import op


revision = "20260608_0025"
down_revision = "20260608_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_template_send_logs_phone_number_id",
        "template_send_logs",
        ["phone_number_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_send_logs_phone_number_id", table_name="template_send_logs")
