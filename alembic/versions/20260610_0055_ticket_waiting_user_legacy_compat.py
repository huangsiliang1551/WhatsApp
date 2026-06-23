"""allow legacy waiting_user ticket rows at the database constraint layer

Revision ID: 20260610_0055
Revises: 20260610_0054
Create Date: 2026-06-10 22:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260610_0055"
down_revision: str | None = "20260610_0054"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_LEGACY_COMPATIBLE_TICKET_STATUS_CHECK = (
    "status IN ('open', 'in_progress', 'waiting_user', 'pending_user', "
    "'resolved', 'rejected', 'closed', 'cancelled')"
)
_CANONICAL_TICKET_STATUS_CHECK = (
    "status IN ('open', 'in_progress', 'pending_user', 'resolved', 'rejected', 'closed', 'cancelled')"
)


def upgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("ck_tickets_status", type_="check")
        batch_op.create_check_constraint(
            "ck_tickets_status",
            _LEGACY_COMPATIBLE_TICKET_STATUS_CHECK,
        )


def downgrade() -> None:
    op.execute("UPDATE tickets SET status = 'pending_user' WHERE status = 'waiting_user'")
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("ck_tickets_status", type_="check")
        batch_op.create_check_constraint(
            "ck_tickets_status",
            _CANONICAL_TICKET_STATUS_CHECK,
        )
