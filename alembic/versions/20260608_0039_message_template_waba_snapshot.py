"""Add direct WABA snapshot to message templates.

Revision ID: 20260608_0039
Revises: 20260608_0038
Create Date: 2026-06-09 00:50:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0039"
down_revision = "20260608_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "message_templates",
        sa.Column("waba_id", sa.String(length=128), nullable=True),
    )

    op.execute(
        """
        UPDATE message_templates
        SET waba_id = (
            SELECT whatsapp_business_accounts.waba_id
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.id = message_templates.waba_account_id
        )
        WHERE waba_account_id IS NOT NULL
        """
    )

    op.create_index(
        "ix_message_templates_waba_id",
        "message_templates",
        ["waba_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_templates_waba_id", table_name="message_templates")

    with op.batch_alter_table("message_templates") as batch_op:
        batch_op.drop_column("waba_id")
