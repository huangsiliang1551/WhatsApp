"""add media asset provider sync table

Revision ID: 20260607_0009
Revises: 20260607_0008
Create Date: 2026-06-08 01:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260607_0009"
down_revision: str | None = "20260607_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_asset_provider_syncs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("provider_name", sa.String(length=32), nullable=False),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("meta_media_id", sa.String(length=255), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_id",
            "provider_name",
            "phone_number_id",
            name="uq_media_asset_provider_syncs_scope",
        ),
    )
    op.create_index(
        "ix_media_asset_provider_syncs_account_id",
        "media_asset_provider_syncs",
        ["account_id"],
    )
    op.create_index(
        "ix_media_asset_provider_syncs_asset_id",
        "media_asset_provider_syncs",
        ["asset_id"],
    )
    op.create_index(
        "ix_media_asset_provider_syncs_provider_name",
        "media_asset_provider_syncs",
        ["provider_name"],
    )
    op.create_index(
        "ix_media_asset_provider_syncs_waba_id",
        "media_asset_provider_syncs",
        ["waba_id"],
    )
    op.create_index(
        "ix_media_asset_provider_syncs_phone_number_id",
        "media_asset_provider_syncs",
        ["phone_number_id"],
    )
    op.create_index(
        "ix_media_asset_provider_syncs_meta_media_id",
        "media_asset_provider_syncs",
        ["meta_media_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_media_asset_provider_syncs_meta_media_id",
        table_name="media_asset_provider_syncs",
    )
    op.drop_index(
        "ix_media_asset_provider_syncs_phone_number_id",
        table_name="media_asset_provider_syncs",
    )
    op.drop_index(
        "ix_media_asset_provider_syncs_waba_id",
        table_name="media_asset_provider_syncs",
    )
    op.drop_index(
        "ix_media_asset_provider_syncs_provider_name",
        table_name="media_asset_provider_syncs",
    )
    op.drop_index(
        "ix_media_asset_provider_syncs_asset_id",
        table_name="media_asset_provider_syncs",
    )
    op.drop_index(
        "ix_media_asset_provider_syncs_account_id",
        table_name="media_asset_provider_syncs",
    )
    op.drop_table("media_asset_provider_syncs")
