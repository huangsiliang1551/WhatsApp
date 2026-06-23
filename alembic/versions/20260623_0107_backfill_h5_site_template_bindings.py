"""Backfill H5 site template bindings from legacy agency templates.

Revision ID: 20260623_0107
Revises: 20260623_0106
Create Date: 2026-06-23 01:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260623_0107"
down_revision = "20260623_0106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    h5_sites = sa.table(
        "h5_sites",
        sa.column("id", sa.String(length=36)),
        sa.column("agency_id", sa.String(length=36)),
        sa.column("metadata_json", sa.JSON()),
    )
    agency_templates = sa.table(
        "agency_templates",
        sa.column("agency_id", sa.String(length=36)),
        sa.column("template_id", sa.String(length=36)),
    )

    rows = bind.execute(
        sa.select(
            h5_sites.c.id,
            h5_sites.c.metadata_json,
            agency_templates.c.template_id,
        ).select_from(
            h5_sites.outerjoin(
                agency_templates,
                h5_sites.c.agency_id == agency_templates.c.agency_id,
            )
        )
    ).all()

    for site_id, metadata_json, template_id in rows:
        if not template_id:
            continue
        metadata = dict(metadata_json or {})
        existing_template_id = metadata.get("template_id")
        if isinstance(existing_template_id, str) and existing_template_id:
            continue
        metadata["template_id"] = template_id
        bind.execute(
            sa.update(h5_sites)
            .where(h5_sites.c.id == site_id)
            .values(metadata_json=metadata)
        )


def downgrade() -> None:
    # Data-only backfill; keep site-level bindings intact on downgrade.
    pass
