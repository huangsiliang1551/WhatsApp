"""expand whatsapp daily stats counters

Revision ID: 20260607_0007
Revises: 20260607_0006
Create Date: 2026-06-07 12:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260607_0007"
down_revision: str | Sequence[str] | None = "20260607_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_daily_stats",
        sa.Column("inbound_message_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "whatsapp_daily_stats",
        sa.Column("outbound_message_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "whatsapp_daily_stats",
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "whatsapp_daily_stats",
        sa.Column("read_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "whatsapp_daily_stats",
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "whatsapp_daily_stats",
        sa.Column("unique_customer_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("whatsapp_daily_stats", "unique_customer_count")
    op.drop_column("whatsapp_daily_stats", "failed_count")
    op.drop_column("whatsapp_daily_stats", "read_count")
    op.drop_column("whatsapp_daily_stats", "delivered_count")
    op.drop_column("whatsapp_daily_stats", "outbound_message_count")
    op.drop_column("whatsapp_daily_stats", "inbound_message_count")
