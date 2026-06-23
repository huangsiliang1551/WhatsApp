"""add stats and media asset tables

Revision ID: 20260607_0005
Revises: 20260607_0004
Create Date: 2026-06-07 22:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260607_0005"
down_revision: str | None = "20260607_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "template_daily_stats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("template_name", sa.String(length=100), nullable=False),
        sa.Column("template_code", sa.String(length=255), nullable=True),
        sa.Column("template_category", sa.String(length=32), nullable=False),
        sa.Column("template_language", sa.String(length=16), nullable=False),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("read_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(12, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["template_id"], ["message_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "date",
            "account_id",
            "template_id",
            "waba_id",
            "phone_number_id",
            "template_name",
            "template_language",
            name="uq_template_daily_stats_scope",
        ),
    )
    op.create_index("ix_template_daily_stats_date", "template_daily_stats", ["date"])
    op.create_index("ix_template_daily_stats_account_id", "template_daily_stats", ["account_id"])
    op.create_index("ix_template_daily_stats_template_id", "template_daily_stats", ["template_id"])
    op.create_index("ix_template_daily_stats_waba_id", "template_daily_stats", ["waba_id"])
    op.create_index(
        "ix_template_daily_stats_phone_number_id",
        "template_daily_stats",
        ["phone_number_id"],
    )
    op.create_index(
        "ix_template_daily_stats_template_name",
        "template_daily_stats",
        ["template_name"],
    )

    op.create_table(
        "whatsapp_daily_stats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("conversation_origin_type", sa.String(length=32), nullable=True),
        sa.Column("conversation_category", sa.String(length=32), nullable=True),
        sa.Column("pricing_model", sa.String(length=64), nullable=True),
        sa.Column("billable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("billable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(12, 4), nullable=True),
        sa.Column("hour_bucket", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "date",
            "account_id",
            "waba_id",
            "phone_number_id",
            "conversation_origin_type",
            "conversation_category",
            "pricing_model",
            "hour_bucket",
            name="uq_whatsapp_daily_stats_scope",
        ),
    )
    op.create_index("ix_whatsapp_daily_stats_date", "whatsapp_daily_stats", ["date"])
    op.create_index("ix_whatsapp_daily_stats_account_id", "whatsapp_daily_stats", ["account_id"])
    op.create_index("ix_whatsapp_daily_stats_waba_id", "whatsapp_daily_stats", ["waba_id"])
    op.create_index(
        "ix_whatsapp_daily_stats_phone_number_id",
        "whatsapp_daily_stats",
        ["phone_number_id"],
    )
    op.create_index(
        "ix_whatsapp_daily_stats_conversation_origin_type",
        "whatsapp_daily_stats",
        ["conversation_origin_type"],
    )
    op.create_index(
        "ix_whatsapp_daily_stats_conversation_category",
        "whatsapp_daily_stats",
        ["conversation_category"],
    )
    op.create_index(
        "ix_whatsapp_daily_stats_pricing_model",
        "whatsapp_daily_stats",
        ["pricing_model"],
    )

    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("storage_url", sa.String(length=1024), nullable=True),
        sa.Column("meta_media_id", sa.String(length=255), nullable=True),
        sa.Column("meta_media_status", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual_upload"),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["phone_number_id"], ["whatsapp_phone_numbers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_assets_account_id", "media_assets", ["account_id"])
    op.create_index("ix_media_assets_waba_id", "media_assets", ["waba_id"])
    op.create_index("ix_media_assets_phone_number_id", "media_assets", ["phone_number_id"])
    op.create_index("ix_media_assets_asset_type", "media_assets", ["asset_type"])
    op.create_index("ix_media_assets_storage_key", "media_assets", ["storage_key"])
    op.create_index("ix_media_assets_meta_media_id", "media_assets", ["meta_media_id"])

    op.create_table(
        "media_asset_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("meta_media_id", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_asset_events_account_id", "media_asset_events", ["account_id"])
    op.create_index("ix_media_asset_events_asset_id", "media_asset_events", ["asset_id"])
    op.create_index(
        "ix_media_asset_events_phone_number_id",
        "media_asset_events",
        ["phone_number_id"],
    )
    op.create_index("ix_media_asset_events_event_type", "media_asset_events", ["event_type"])
    op.create_index(
        "ix_media_asset_events_meta_media_id",
        "media_asset_events",
        ["meta_media_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_media_asset_events_meta_media_id", table_name="media_asset_events")
    op.drop_index("ix_media_asset_events_event_type", table_name="media_asset_events")
    op.drop_index("ix_media_asset_events_phone_number_id", table_name="media_asset_events")
    op.drop_index("ix_media_asset_events_asset_id", table_name="media_asset_events")
    op.drop_index("ix_media_asset_events_account_id", table_name="media_asset_events")
    op.drop_table("media_asset_events")

    op.drop_index("ix_media_assets_meta_media_id", table_name="media_assets")
    op.drop_index("ix_media_assets_storage_key", table_name="media_assets")
    op.drop_index("ix_media_assets_asset_type", table_name="media_assets")
    op.drop_index("ix_media_assets_phone_number_id", table_name="media_assets")
    op.drop_index("ix_media_assets_waba_id", table_name="media_assets")
    op.drop_index("ix_media_assets_account_id", table_name="media_assets")
    op.drop_table("media_assets")

    op.drop_index("ix_whatsapp_daily_stats_pricing_model", table_name="whatsapp_daily_stats")
    op.drop_index(
        "ix_whatsapp_daily_stats_conversation_category",
        table_name="whatsapp_daily_stats",
    )
    op.drop_index(
        "ix_whatsapp_daily_stats_conversation_origin_type",
        table_name="whatsapp_daily_stats",
    )
    op.drop_index("ix_whatsapp_daily_stats_phone_number_id", table_name="whatsapp_daily_stats")
    op.drop_index("ix_whatsapp_daily_stats_waba_id", table_name="whatsapp_daily_stats")
    op.drop_index("ix_whatsapp_daily_stats_account_id", table_name="whatsapp_daily_stats")
    op.drop_index("ix_whatsapp_daily_stats_date", table_name="whatsapp_daily_stats")
    op.drop_table("whatsapp_daily_stats")

    op.drop_index("ix_template_daily_stats_template_name", table_name="template_daily_stats")
    op.drop_index("ix_template_daily_stats_phone_number_id", table_name="template_daily_stats")
    op.drop_index("ix_template_daily_stats_waba_id", table_name="template_daily_stats")
    op.drop_index("ix_template_daily_stats_template_id", table_name="template_daily_stats")
    op.drop_index("ix_template_daily_stats_account_id", table_name="template_daily_stats")
    op.drop_index("ix_template_daily_stats_date", table_name="template_daily_stats")
    op.drop_table("template_daily_stats")
