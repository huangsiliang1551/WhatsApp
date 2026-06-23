"""Add direct WABA snapshot to Meta phone numbers and webhook subscriptions.

Revision ID: 20260608_0038
Revises: 20260608_0037
Create Date: 2026-06-09 00:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0038"
down_revision = "20260608_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column("waba_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "webhook_subscriptions",
        sa.Column("waba_id", sa.String(length=128), nullable=True),
    )

    op.execute(
        """
        UPDATE whatsapp_phone_numbers
        SET waba_id = (
            SELECT whatsapp_business_accounts.waba_id
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.id = whatsapp_phone_numbers.waba_account_id
        )
        """
    )
    op.execute(
        """
        UPDATE webhook_subscriptions
        SET waba_id = (
            SELECT whatsapp_business_accounts.waba_id
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.id = webhook_subscriptions.waba_account_id
        )
        """
    )

    with op.batch_alter_table("whatsapp_phone_numbers") as batch_op:
        batch_op.alter_column(
            "waba_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.alter_column(
            "waba_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )

    op.create_index(
        "ix_whatsapp_phone_numbers_waba_id",
        "whatsapp_phone_numbers",
        ["waba_id"],
    )
    op.create_index(
        "ix_webhook_subscriptions_waba_id",
        "webhook_subscriptions",
        ["waba_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_subscriptions_waba_id", table_name="webhook_subscriptions")
    op.drop_index("ix_whatsapp_phone_numbers_waba_id", table_name="whatsapp_phone_numbers")

    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.drop_column("waba_id")
    with op.batch_alter_table("whatsapp_phone_numbers") as batch_op:
        batch_op.drop_column("waba_id")
