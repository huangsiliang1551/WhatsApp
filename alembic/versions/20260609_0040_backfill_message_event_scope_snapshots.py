"""backfill message event scope snapshot fields

Revision ID: 20260609_0040
Revises: 20260608_0039
Create Date: 2026-06-09 10:15:00
"""

from __future__ import annotations

from alembic import op


revision = "20260609_0040"
down_revision = "20260608_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prefer the message-bound phone snapshot when available.
    op.execute(
        """
        UPDATE message_events
        SET phone_number_id = (
            SELECT whatsapp_phone_numbers.phone_number_id
            FROM messages
            JOIN whatsapp_phone_numbers
              ON whatsapp_phone_numbers.id = messages.phone_number_id
            WHERE messages.id = message_events.message_id
        )
        WHERE phone_number_id IS NULL
          AND message_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE message_events
        SET waba_id = (
            SELECT whatsapp_phone_numbers.waba_id
            FROM messages
            JOIN whatsapp_phone_numbers
              ON whatsapp_phone_numbers.id = messages.phone_number_id
            WHERE messages.id = message_events.message_id
        )
        WHERE waba_id IS NULL
          AND message_id IS NOT NULL
        """
    )

    # Fall back to the conversation-bound phone snapshot for orphaned status events.
    op.execute(
        """
        UPDATE message_events
        SET phone_number_id = (
            SELECT whatsapp_phone_numbers.phone_number_id
            FROM conversations
            JOIN whatsapp_phone_numbers
              ON whatsapp_phone_numbers.id = conversations.phone_number_id
            WHERE conversations.id = message_events.conversation_id
        )
        WHERE phone_number_id IS NULL
          AND conversation_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE message_events
        SET waba_id = (
            SELECT whatsapp_phone_numbers.waba_id
            FROM conversations
            JOIN whatsapp_phone_numbers
              ON whatsapp_phone_numbers.id = conversations.phone_number_id
            WHERE conversations.id = message_events.conversation_id
        )
        WHERE waba_id IS NULL
          AND conversation_id IS NOT NULL
        """
    )

    # If a provider phone number snapshot already exists on the event row, derive the WABA snapshot from it.
    op.execute(
        """
        UPDATE message_events
        SET waba_id = (
            SELECT whatsapp_phone_numbers.waba_id
            FROM whatsapp_phone_numbers
            WHERE whatsapp_phone_numbers.phone_number_id = message_events.phone_number_id
        )
        WHERE waba_id IS NULL
          AND phone_number_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # Historical backfill only; leave populated snapshots in place on downgrade.
    return None
