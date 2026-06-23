"""add webhook runtime health fields to waba accounts

Revision ID: 20260608_0016
Revises: 20260608_0015
Create Date: 2026-06-08 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260608_0016"
down_revision: str | None = "20260608_0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column(
            "webhook_verification_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column("webhook_last_verified_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column("webhook_last_verification_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column(
            "webhook_runtime_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column("webhook_last_event_received_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column("webhook_last_message_received_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column("webhook_last_status_update_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column("webhook_last_signature_failed_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column(
            "webhook_signature_failure_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column("webhook_runtime_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("whatsapp_business_accounts", "webhook_runtime_error")
    op.drop_column("whatsapp_business_accounts", "webhook_signature_failure_count")
    op.drop_column("whatsapp_business_accounts", "webhook_last_signature_failed_at")
    op.drop_column("whatsapp_business_accounts", "webhook_last_status_update_at")
    op.drop_column("whatsapp_business_accounts", "webhook_last_message_received_at")
    op.drop_column("whatsapp_business_accounts", "webhook_last_event_received_at")
    op.drop_column("whatsapp_business_accounts", "webhook_runtime_status")
    op.drop_column("whatsapp_business_accounts", "webhook_last_verification_error")
    op.drop_column("whatsapp_business_accounts", "webhook_last_verified_at")
    op.drop_column("whatsapp_business_accounts", "webhook_verification_status")
