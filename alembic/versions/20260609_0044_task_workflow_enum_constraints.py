"""add task workflow enum check constraints

Revision ID: 20260609_0044
Revises: 20260609_0043
Create Date: 2026-06-09 18:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260609_0044"
down_revision: str | None = "20260609_0043"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_TASK_INSTANCE_STATUS_CHECK = (
    "status IN ("
    "'available', 'claimed', 'submitted', 'under_review', 'changes_requested', "
    "'approved', 'rejected', 'appealing', 'completed', 'expired', 'abandoned', 'cancelled'"
    ")"
)
_TASK_SUBMISSION_STATUS_CHECK = (
    "status IN ("
    "'draft', 'submitted', 'under_review', 'changes_requested', 'approved', 'rejected', 'withdrawn'"
    ")"
)
_TASK_REVIEW_DECISION_CHECK = (
    "decision IN ('pending', 'approved', 'rejected', 'changes_requested', 'escalated')"
)
_TICKET_TYPE_CHECK = (
    "ticket_type IN ('submission_review', 'appeal', 'help', 'complaint', 'manual_service')"
)


def upgrade() -> None:
    _assert_allowed_values(
        table_name="task_instances",
        column_name="status",
        allowed_values=(
            "available",
            "claimed",
            "submitted",
            "under_review",
            "changes_requested",
            "approved",
            "rejected",
            "appealing",
            "completed",
            "expired",
            "abandoned",
            "cancelled",
        ),
    )
    _assert_allowed_values(
        table_name="task_submissions",
        column_name="status",
        allowed_values=(
            "draft",
            "submitted",
            "under_review",
            "changes_requested",
            "approved",
            "rejected",
            "withdrawn",
        ),
    )
    _assert_allowed_values(
        table_name="task_review_decisions",
        column_name="decision",
        allowed_values=("pending", "approved", "rejected", "changes_requested", "escalated"),
    )
    _assert_allowed_values(
        table_name="tickets",
        column_name="ticket_type",
        allowed_values=("submission_review", "appeal", "help", "complaint", "manual_service"),
    )

    with op.batch_alter_table("task_instances") as batch_op:
        batch_op.create_check_constraint("ck_task_instances_status", _TASK_INSTANCE_STATUS_CHECK)

    with op.batch_alter_table("task_submissions") as batch_op:
        batch_op.create_check_constraint("ck_task_submissions_status", _TASK_SUBMISSION_STATUS_CHECK)

    with op.batch_alter_table("task_review_decisions") as batch_op:
        batch_op.create_check_constraint("ck_task_review_decisions_decision", _TASK_REVIEW_DECISION_CHECK)

    with op.batch_alter_table("tickets") as batch_op:
        batch_op.create_check_constraint("ck_tickets_ticket_type", _TICKET_TYPE_CHECK)


def downgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("ck_tickets_ticket_type", type_="check")

    with op.batch_alter_table("task_review_decisions") as batch_op:
        batch_op.drop_constraint("ck_task_review_decisions_decision", type_="check")

    with op.batch_alter_table("task_submissions") as batch_op:
        batch_op.drop_constraint("ck_task_submissions_status", type_="check")

    with op.batch_alter_table("task_instances") as batch_op:
        batch_op.drop_constraint("ck_task_instances_status", type_="check")


def _assert_allowed_values(
    *,
    table_name: str,
    column_name: str,
    allowed_values: tuple[str, ...],
) -> None:
    connection = op.get_bind()
    table = sa.table(
        table_name,
        sa.column(column_name, sa.String(length=32)),
    )
    invalid_rows = connection.execute(
        sa.select(table.c[column_name])
        .where(~table.c[column_name].in_(allowed_values))
        .group_by(table.c[column_name])
    ).all()
    if invalid_rows:
        invalid_values = ", ".join(sorted(str(row[0]) for row in invalid_rows))
        raise RuntimeError(
            f"Cannot add enum constraint on {table_name}.{column_name}; "
            f"unexpected values remain: {invalid_values}."
        )
