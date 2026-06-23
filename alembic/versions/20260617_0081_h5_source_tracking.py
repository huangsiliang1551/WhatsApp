"""Add site_key column to conversations, tickets, and mkt_task_instances for H5 source tracking.

Revision ID: 20260617_0081
Revises: 20260617_0080
Create Date: 2026-06-17 06:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0081"
down_revision: str | None = "20260617_0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Conversation
    op.add_column("conversations", sa.Column("site_key", sa.String(50), nullable=True))
    op.create_index("ix_conversations_site_key", "conversations", ["site_key"])

    # Ticket
    op.add_column("tickets", sa.Column("site_key", sa.String(50), nullable=True))
    op.create_index("ix_tickets_site_key", "tickets", ["site_key"])

    # MktTaskInstance
    op.add_column("mkt_task_instances", sa.Column("site_key", sa.String(50), nullable=True))
    op.create_index("ix_mkt_task_instances_site_key", "mkt_task_instances", ["site_key"])


def downgrade() -> None:
    op.drop_index("ix_mkt_task_instances_site_key", table_name="mkt_task_instances")
    op.drop_column("mkt_task_instances", "site_key")
    op.drop_index("ix_tickets_site_key", table_name="tickets")
    op.drop_column("tickets", "site_key")
    op.drop_index("ix_conversations_site_key", table_name="conversations")
    op.drop_column("conversations", "site_key")
