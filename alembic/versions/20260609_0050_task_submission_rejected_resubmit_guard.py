"""extend task submission duplicate guard to rejected submissions

Revision ID: 20260609_0050
Revises: 20260609_0049
Create Date: 2026-06-09 13:45:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260609_0050"
down_revision = "20260609_0049"
branch_labels = None
depends_on = None


_INDEX_NAME = "uq_task_submissions_active_per_task_instance"
_REJECTED_GUARD_SCOPE = "status IN ('submitted', 'under_review', 'rejected')"
_LEGACY_SCOPE = "status IN ('submitted', 'under_review')"


def upgrade() -> None:
    _assert_no_rejected_resubmit_conflicts()
    op.drop_index(_INDEX_NAME, table_name="task_submissions")
    op.create_index(
        _INDEX_NAME,
        "task_submissions",
        ["task_instance_id"],
        unique=True,
        sqlite_where=sa.text(_REJECTED_GUARD_SCOPE),
        postgresql_where=sa.text(_REJECTED_GUARD_SCOPE),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="task_submissions")
    op.create_index(
        _INDEX_NAME,
        "task_submissions",
        ["task_instance_id"],
        unique=True,
        sqlite_where=sa.text(_LEGACY_SCOPE),
        postgresql_where=sa.text(_LEGACY_SCOPE),
    )


def _assert_no_rejected_resubmit_conflicts() -> None:
    connection = op.get_bind()
    conflicting_rows = connection.execute(
        sa.text(
            """
            SELECT task_instance_id
            FROM task_submissions
            WHERE status IN ('submitted', 'under_review', 'rejected')
            GROUP BY task_instance_id
            HAVING COUNT(*) > 1
            ORDER BY task_instance_id
            LIMIT 5
            """
        )
    ).fetchall()
    if conflicting_rows:
        sample_ids = ", ".join(str(row[0]) for row in conflicting_rows)
        raise RuntimeError(
            "Cannot extend the task submission rejected-resubmit guard; "
            "task instances still have multiple submitted/under_review/rejected rows: "
            f"{sample_ids}."
        )
