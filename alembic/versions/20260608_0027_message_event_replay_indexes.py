"""add message event replay indexes

Revision ID: 20260608_0027
Revises: 20260608_0026
Create Date: 2026-06-08 23:30:00
"""

from __future__ import annotations

from alembic import op


revision = "20260608_0027"
down_revision = "20260608_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_message_events_account_event_created",
        "message_events",
        ["account_id", "event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_message_events_conversation_id",
        "message_events",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_message_events_message_id",
        "message_events",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_message_events_message_id", table_name="message_events")
    op.drop_index("ix_message_events_conversation_id", table_name="message_events")
    op.drop_index("ix_message_events_account_event_created", table_name="message_events")
