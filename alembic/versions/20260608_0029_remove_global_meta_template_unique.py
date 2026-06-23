"""remove global meta template unique constraint

Revision ID: 20260608_0029
Revises: 20260608_0028
Create Date: 2026-06-08 23:58:00
"""

from __future__ import annotations

from alembic import op


revision = "20260608_0029"
down_revision = "20260608_0028"
branch_labels = None
depends_on = None


SQLITE_NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s",
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "message_templates",
            recreate="always",
            naming_convention=SQLITE_NAMING_CONVENTION,
        ) as batch_op:
            batch_op.drop_constraint(
                "uq_message_templates_meta_template_id",
                type_="unique",
            )
        return

    op.drop_constraint(
        "uq_message_templates_meta_template_id",
        "message_templates",
        type_="unique",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("message_templates") as batch_op:
            batch_op.create_unique_constraint(
                "uq_message_templates_meta_template_id",
                ["meta_template_id"],
            )
        return

    op.create_unique_constraint(
        "uq_message_templates_meta_template_id",
        "message_templates",
        ["meta_template_id"],
    )
