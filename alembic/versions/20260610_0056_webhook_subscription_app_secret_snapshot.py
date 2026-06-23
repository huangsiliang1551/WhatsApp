"""Persist webhook subscription app secret snapshots.

Revision ID: 20260610_0056
Revises: 20260610_0055
Create Date: 2026-06-10 23:15:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260610_0056"
down_revision: str | None = "20260610_0055"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "webhook_subscriptions",
        sa.Column("app_secret", sa.String(length=255), nullable=True),
    )

    op.execute(
        """
        UPDATE webhook_subscriptions
        SET app_secret = NULLIF((
            SELECT TRIM(whatsapp_business_accounts.app_secret)
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.id = webhook_subscriptions.waba_account_id
              AND whatsapp_business_accounts.account_id = webhook_subscriptions.account_id
        ), '')
        WHERE app_secret IS NULL
        """
    )
    op.execute(
        """
        UPDATE webhook_subscriptions
        SET app_secret = NULLIF((
            SELECT TRIM(whatsapp_business_accounts.app_secret)
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.account_id = webhook_subscriptions.account_id
              AND whatsapp_business_accounts.waba_id = webhook_subscriptions.waba_id
            ORDER BY whatsapp_business_accounts.updated_at DESC,
                     whatsapp_business_accounts.created_at DESC,
                     whatsapp_business_accounts.id DESC
            LIMIT 1
        ), '')
        WHERE app_secret IS NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.drop_column("app_secret")
