"""add WABA scope to media asset events

Revision ID: 20260608_0030
Revises: 20260608_0029
Create Date: 2026-06-08 23:59:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0030"
down_revision = "20260608_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_asset_events",
        sa.Column("waba_id", sa.String(length=128), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE media_asset_events
            SET waba_id = (
                SELECT media_assets.waba_id
                FROM media_assets
                WHERE media_assets.id = media_asset_events.asset_id
            )
            WHERE waba_id IS NULL
            """
        )
    )
    op.create_index(
        "ix_media_asset_events_waba_id",
        "media_asset_events",
        ["waba_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_media_asset_events_waba_id", table_name="media_asset_events")
    op.drop_column("media_asset_events", "waba_id")
