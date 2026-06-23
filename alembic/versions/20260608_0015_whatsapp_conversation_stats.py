"""add whatsapp conversation stats table

Revision ID: 20260608_0015
Revises: 20260608_0014
Create Date: 2026-06-08 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260608_0015"
down_revision: str | None = "20260608_0014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_conversation_stats",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=128), nullable=False),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("conversation_origin_type", sa.String(length=32), nullable=True),
        sa.Column("conversation_category", sa.String(length=32), nullable=True),
        sa.Column("pricing_model", sa.String(length=64), nullable=True),
        sa.Column("billable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("billable_key", sa.String(length=255), nullable=True),
        sa.Column("inbound_message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outbound_message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("read_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(12, 4), nullable=True),
        sa.Column("hour_bucket", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.UniqueConstraint(
            "date",
            "account_id",
            "conversation_id",
            "waba_id",
            "phone_number_id",
            "conversation_origin_type",
            "conversation_category",
            "pricing_model",
            "billable",
            "billable_key",
            "hour_bucket",
            name="uq_whatsapp_conversation_stats_scope",
        ),
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_date",
        "whatsapp_conversation_stats",
        ["date"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_account_id",
        "whatsapp_conversation_stats",
        ["account_id"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_conversation_id",
        "whatsapp_conversation_stats",
        ["conversation_id"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_customer_id",
        "whatsapp_conversation_stats",
        ["customer_id"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_waba_id",
        "whatsapp_conversation_stats",
        ["waba_id"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_phone_number_id",
        "whatsapp_conversation_stats",
        ["phone_number_id"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_conversation_origin_type",
        "whatsapp_conversation_stats",
        ["conversation_origin_type"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_conversation_category",
        "whatsapp_conversation_stats",
        ["conversation_category"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_pricing_model",
        "whatsapp_conversation_stats",
        ["pricing_model"],
    )
    op.create_index(
        "ix_whatsapp_conversation_stats_billable_key",
        "whatsapp_conversation_stats",
        ["billable_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_whatsapp_conversation_stats_billable_key", table_name="whatsapp_conversation_stats")
    op.drop_index("ix_whatsapp_conversation_stats_pricing_model", table_name="whatsapp_conversation_stats")
    op.drop_index(
        "ix_whatsapp_conversation_stats_conversation_category",
        table_name="whatsapp_conversation_stats",
    )
    op.drop_index(
        "ix_whatsapp_conversation_stats_conversation_origin_type",
        table_name="whatsapp_conversation_stats",
    )
    op.drop_index("ix_whatsapp_conversation_stats_phone_number_id", table_name="whatsapp_conversation_stats")
    op.drop_index("ix_whatsapp_conversation_stats_waba_id", table_name="whatsapp_conversation_stats")
    op.drop_index("ix_whatsapp_conversation_stats_customer_id", table_name="whatsapp_conversation_stats")
    op.drop_index("ix_whatsapp_conversation_stats_conversation_id", table_name="whatsapp_conversation_stats")
    op.drop_index("ix_whatsapp_conversation_stats_account_id", table_name="whatsapp_conversation_stats")
    op.drop_index("ix_whatsapp_conversation_stats_date", table_name="whatsapp_conversation_stats")
    op.drop_table("whatsapp_conversation_stats")
