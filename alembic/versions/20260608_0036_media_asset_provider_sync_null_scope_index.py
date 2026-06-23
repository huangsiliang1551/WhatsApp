"""add nullable-scope unique index for media asset provider syncs

Revision ID: 20260608_0036
Revises: 20260608_0035
Create Date: 2026-06-08 23:59:36
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0036"
down_revision = "20260608_0035"
branch_labels = None
depends_on = None


INDEX_NAME = "ux_media_asset_provider_syncs_scope_nulls_not_distinct"
TABLE_NAME = "media_asset_provider_syncs"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        [
            sa.text("asset_id"),
            sa.text("provider_name"),
            sa.text("coalesce(phone_number_id, '__NULL__')"),
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
