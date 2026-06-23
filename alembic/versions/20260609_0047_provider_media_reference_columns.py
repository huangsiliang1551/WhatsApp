"""add provider-first media reference columns

Revision ID: 20260609_0047
Revises: 20260609_0046
Create Date: 2026-06-09 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260609_0047"
down_revision: str | None = "20260609_0046"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.add_column(sa.Column("header_media_provider_media_id", sa.String(length=255), nullable=True))

    with op.batch_alter_table("media_asset_provider_syncs") as batch_op:
        batch_op.add_column(sa.Column("provider_media_id", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_media_asset_provider_syncs_provider_media_id", ["provider_media_id"], unique=False)

    with op.batch_alter_table("media_asset_events") as batch_op:
        batch_op.add_column(sa.Column("provider_media_id", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_media_asset_events_provider_media_id", ["provider_media_id"], unique=False)

    op.execute(
        """
        UPDATE template_send_logs
        SET header_media_provider_media_id = header_media_meta_media_id
        WHERE header_media_provider_media_id IS NULL
          AND header_media_meta_media_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE media_asset_provider_syncs
        SET provider_media_id = meta_media_id
        WHERE provider_media_id IS NULL
          AND meta_media_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE media_asset_events
        SET provider_media_id = meta_media_id
        WHERE provider_media_id IS NULL
          AND meta_media_id IS NOT NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("media_asset_events") as batch_op:
        batch_op.drop_index("ix_media_asset_events_provider_media_id")
        batch_op.drop_column("provider_media_id")

    with op.batch_alter_table("media_asset_provider_syncs") as batch_op:
        batch_op.drop_index("ix_media_asset_provider_syncs_provider_media_id")
        batch_op.drop_column("provider_media_id")

    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.drop_column("header_media_provider_media_id")
