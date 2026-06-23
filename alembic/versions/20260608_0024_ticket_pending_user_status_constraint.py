"""normalize ticket pending user status constraint

Revision ID: 20260608_0024
Revises: 20260608_0023
Create Date: 2026-06-08 10:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0024"
down_revision = "20260608_0023"
branch_labels = None
depends_on = None


_TICKET_STATUS_CHECK = (
    "status IN ('open', 'in_progress', 'pending_user', 'resolved', 'rejected', 'closed', 'cancelled')"
)


def upgrade() -> None:
    tickets = sa.table("tickets", sa.column("status", sa.String(length=32)))
    op.execute(
        tickets.update()
        .where(tickets.c.status == "waiting_user")
        .values(status="pending_user")
    )
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.create_check_constraint("ck_tickets_status", _TICKET_STATUS_CHECK)


def downgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("ck_tickets_status", type_="check")
