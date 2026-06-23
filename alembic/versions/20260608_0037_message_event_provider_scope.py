"""add provider scope fields to message events

Revision ID: 20260608_0037
Revises: 20260608_0036
Create Date: 2026-06-08 23:59:37
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0037"
down_revision = "20260608_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("message_events", sa.Column("provider_name", sa.String(length=32), nullable=True))
    op.add_column("message_events", sa.Column("waba_id", sa.String(length=128), nullable=True))
    op.add_column("message_events", sa.Column("phone_number_id", sa.String(length=128), nullable=True))
    op.add_column("message_events", sa.Column("provider_event_id", sa.String(length=255), nullable=True))
    op.add_column("message_events", sa.Column("occurred_at", sa.DateTime(timezone=False), nullable=True))
    op.create_index("ix_message_events_provider_name", "message_events", ["provider_name"])
    op.create_index("ix_message_events_waba_id", "message_events", ["waba_id"])
    op.create_index("ix_message_events_phone_number_id", "message_events", ["phone_number_id"])
    op.create_index("ix_message_events_occurred_at", "message_events", ["occurred_at"])
    op.create_index(
        "uq_message_events_account_provider_event",
        "message_events",
        ["account_id", "provider_name", "provider_event_id"],
        unique=True,
        sqlite_where=sa.text("provider_name IS NOT NULL AND provider_event_id IS NOT NULL"),
        postgresql_where=sa.text("provider_name IS NOT NULL AND provider_event_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_message_events_account_provider_event", table_name="message_events")
    op.drop_index("ix_message_events_occurred_at", table_name="message_events")
    op.drop_index("ix_message_events_phone_number_id", table_name="message_events")
    op.drop_index("ix_message_events_waba_id", table_name="message_events")
    op.drop_index("ix_message_events_provider_name", table_name="message_events")
    op.drop_column("message_events", "occurred_at")
    op.drop_column("message_events", "provider_event_id")
    op.drop_column("message_events", "phone_number_id")
    op.drop_column("message_events", "waba_id")
    op.drop_column("message_events", "provider_name")
