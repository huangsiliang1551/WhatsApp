"""add phone number linkage and template idempotency

Revision ID: 20260607_0003
Revises: 20260606_0002
Create Date: 2026-06-07 10:45:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260607_0003"
down_revision: str | None = "20260606_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("phone_number_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_messages_phone_number_id",
            "whatsapp_phone_numbers",
            ["phone_number_id"],
            ["id"],
        )

    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.add_column(sa.Column("phone_number_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch_op.create_foreign_key(
            "fk_template_send_logs_phone_number_id",
            "whatsapp_phone_numbers",
            ["phone_number_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_template_send_logs_idempotency_key",
            ["idempotency_key"],
            unique=False,
        )

    op.execute(
        """
        UPDATE messages
        SET phone_number_id = (
            SELECT conversations.phone_number_id
            FROM conversations
            WHERE conversations.id = messages.conversation_id
        )
        WHERE conversation_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE template_send_logs
        SET phone_number_id = (
            SELECT conversations.phone_number_id
            FROM conversations
            WHERE conversations.id = template_send_logs.conversation_id
        )
        WHERE conversation_id IS NOT NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.drop_index("ix_template_send_logs_idempotency_key")
        batch_op.drop_constraint("fk_template_send_logs_phone_number_id", type_="foreignkey")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("phone_number_id")

    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_constraint("fk_messages_phone_number_id", type_="foreignkey")
        batch_op.drop_column("phone_number_id")
