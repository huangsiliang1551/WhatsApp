"""add updated_at to template_send_logs

Revision ID: 698b1cc1f0c7
Revises: 4f06beb1b074
Create Date: 2026-06-16 06:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "698b1cc1f0c7"
down_revision: str | None = "4f06beb1b074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("template_send_logs", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=False),
                    nullable=True,
                )
            )
    else:
        op.add_column(
            "template_send_logs",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=True,
                server_default=text("CURRENT_TIMESTAMP"),
            ),
        )

    op.execute(
        text(
            """
            UPDATE template_send_logs
            SET updated_at = COALESCE(last_status_at, sent_at, created_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL
            """
        )
    )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("template_send_logs", recreate="always") as batch_op:
            batch_op.alter_column(
                "updated_at",
                existing_type=sa.DateTime(timezone=False),
                nullable=False,
                server_default=text("CURRENT_TIMESTAMP"),
            )
    else:
        op.alter_column(
            "template_send_logs",
            "updated_at",
            existing_type=sa.DateTime(timezone=False),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("template_send_logs", recreate="always") as batch_op:
            batch_op.drop_column("updated_at")
        return

    op.drop_column("template_send_logs", "updated_at")
