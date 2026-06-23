"""add provider status event buffer

Revision ID: 20260608_0028
Revises: 20260608_0027
Create Date: 2026-06-08 23:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0028"
down_revision = "20260608_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_status_event_buffer",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("external_status", sa.String(length=64), nullable=False),
        sa.Column("recipient_id", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("seen_count", sa.Integer(), nullable=False),
        sa.Column("replay_state", sa.String(length=32), nullable=False),
        sa.Column("replayed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("replayed_message_event_id", sa.String(length=36), nullable=True),
        sa.Column("replay_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["replayed_message_event_id"], ["message_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "provider_name",
            "provider_message_id",
            "external_status",
            name="uq_provider_status_buffer_status",
        ),
    )
    op.create_index(
        "ix_provider_status_event_buffer_account_id",
        "provider_status_event_buffer",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_status_event_buffer_phone_number_id",
        "provider_status_event_buffer",
        ["phone_number_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_status_event_buffer_waba_id",
        "provider_status_event_buffer",
        ["waba_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_status_buffer_account_state",
        "provider_status_event_buffer",
        ["account_id", "replay_state", "last_seen_at"],
        unique=False,
    )
    op.create_index(
        "ix_provider_status_buffer_provider_message",
        "provider_status_event_buffer",
        ["account_id", "provider_name", "provider_message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_status_buffer_provider_message", table_name="provider_status_event_buffer")
    op.drop_index("ix_provider_status_buffer_account_state", table_name="provider_status_event_buffer")
    op.drop_index("ix_provider_status_event_buffer_waba_id", table_name="provider_status_event_buffer")
    op.drop_index("ix_provider_status_event_buffer_phone_number_id", table_name="provider_status_event_buffer")
    op.drop_index("ix_provider_status_event_buffer_account_id", table_name="provider_status_event_buffer")
    op.drop_table("provider_status_event_buffer")
