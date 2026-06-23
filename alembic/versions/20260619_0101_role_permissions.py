"""Create role_permissions table for fine-grained permission system.

Revision ID: 20260619_0101
Revises: ae789a13b2c5
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

from app.core.permission_defs import DEFAULT_TEMPLATES


revision: str = "20260619_0101"
down_revision: str | None = "ae789a13b2c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), sa.ForeignKey("agencies.id"), nullable=True, index=True),
        sa.Column("role_name", sa.String(50), nullable=False),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("template_name", sa.String(100), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("agency_id", "role_name", name="uq_role_permissions_agency_role"),
    )

    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("id", sa.String(36)),
        sa.column("agency_id", sa.String(36)),
        sa.column("role_name", sa.String(50)),
        sa.column("is_template", sa.Boolean()),
        sa.column("template_name", sa.String(100)),
        sa.column("permissions", sa.JSON()),
        sa.column("created_by", sa.String(36)),
    )

    templates = [
        {
            "id": str(uuid4()),
            "agency_id": None,
            "role_name": role_name,
            "is_template": True,
            "template_name": template["name"],
            "permissions": template["permissions"],
            "created_by": "system",
        }
        for role_name, template in DEFAULT_TEMPLATES.items()
    ]

    op.bulk_insert(role_permissions_table, templates)


def downgrade() -> None:
    op.drop_table("role_permissions")
