"""Treat template send log phone scope as provider snapshot.

Revision ID: 20260609_0049
Revises: 20260609_0048
Create Date: 2026-06-09 19:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260609_0049"
down_revision: str | None = "20260609_0048"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.drop_constraint("fk_template_send_logs_phone_number_id", type_="foreignkey")
        batch_op.alter_column(
            "phone_number_id",
            existing_type=sa.String(length=36),
            type_=sa.String(length=128),
            existing_nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    incompatible_scope = bind.execute(
        sa.text(
            """
            SELECT phone_number_id
            FROM template_send_logs AS template_send_logs
            WHERE phone_number_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM whatsapp_phone_numbers AS whatsapp_phone_numbers
                WHERE whatsapp_phone_numbers.id = template_send_logs.phone_number_id
              )
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if incompatible_scope is not None:
        raise RuntimeError(
            "Cannot downgrade 20260609_0049: template_send_logs.phone_number_id contains "
            "provider snapshot values that are incompatible with whatsapp_phone_numbers.id."
        )
    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.alter_column(
            "phone_number_id",
            existing_type=sa.String(length=128),
            type_=sa.String(length=36),
            existing_nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_template_send_logs_phone_number_id",
            "whatsapp_phone_numbers",
            ["phone_number_id"],
            ["id"],
        )
