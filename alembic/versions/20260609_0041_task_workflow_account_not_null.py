"""tighten task workflow account scope columns to not null

Revision ID: 20260609_0041
Revises: 20260609_0040
Create Date: 2026-06-09 11:20:00
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from alembic import op


revision = "20260609_0041"
down_revision = "20260609_0040"
branch_labels = None
depends_on = None


TARGET_TABLES: tuple[str, ...] = (
    "task_submissions",
    "task_review_decisions",
    "tickets",
)


def upgrade() -> None:
    _backfill_task_workflow_account_ids()
    _assert_no_null_account_ids()

    for table_name in TARGET_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "account_id",
                existing_type=sa.String(length=128),
                nullable=False,
            )


def downgrade() -> None:
    for table_name in reversed(TARGET_TABLES):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "account_id",
                existing_type=sa.String(length=128),
                nullable=True,
            )


def _backfill_task_workflow_account_ids() -> None:
    connection = op.get_bind()

    accounts = sa.table("accounts", sa.column("account_id", sa.String(length=128)))
    h5_sites = sa.table(
        "h5_sites",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("metadata_json", sa.JSON()),
    )
    task_templates = sa.table(
        "task_templates",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("metadata_json", sa.JSON()),
    )
    task_instances = sa.table(
        "task_instances",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("template_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("metadata_json", sa.JSON()),
    )
    task_submissions = sa.table(
        "task_submissions",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("payload_json", sa.JSON()),
    )
    task_review_decisions = sa.table(
        "task_review_decisions",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("submission_id", sa.String(length=36)),
    )
    tickets = sa.table(
        "tickets",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("linked_task_instance_id", sa.String(length=36)),
        sa.column("linked_submission_id", sa.String(length=36)),
        sa.column("review_decision_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("metadata_json", sa.JSON()),
    )

    valid_account_ids = {
        str(row.account_id)
        for row in connection.execute(sa.select(accounts.c.account_id)).mappings()
        if row.account_id is not None
    }

    site_account_map = _backfill_from_metadata(
        connection,
        table=h5_sites,
        id_column=h5_sites.c.id,
        json_column=h5_sites.c.metadata_json,
        valid_account_ids=valid_account_ids,
    )
    template_account_map = _backfill_from_metadata(
        connection,
        table=task_templates,
        id_column=task_templates.c.id,
        json_column=task_templates.c.metadata_json,
        valid_account_ids=valid_account_ids,
    )

    instance_rows = connection.execute(
        sa.select(
            task_instances.c.id,
            task_instances.c.account_id,
            task_instances.c.template_id,
            task_instances.c.site_id,
            task_instances.c.metadata_json,
        )
    ).mappings()
    instance_account_map = _update_from_map(
        connection,
        table=task_instances,
        id_column=task_instances.c.id,
        updates=(
            (
                row.id,
                _first_valid_account_id(
                    valid_account_ids,
                    row.account_id,
                    template_account_map.get(row.template_id),
                    site_account_map.get(row.site_id),
                    _extract_account_id(row.metadata_json),
                ),
            )
            for row in instance_rows
        ),
    )

    submission_rows = connection.execute(
        sa.select(
            task_submissions.c.id,
            task_submissions.c.account_id,
            task_submissions.c.task_instance_id,
            task_submissions.c.site_id,
            task_submissions.c.payload_json,
        )
    ).mappings()
    submission_account_map = _update_from_map(
        connection,
        table=task_submissions,
        id_column=task_submissions.c.id,
        updates=(
            (
                row.id,
                _first_valid_account_id(
                    valid_account_ids,
                    row.account_id,
                    instance_account_map.get(row.task_instance_id),
                    site_account_map.get(row.site_id),
                    _extract_account_id(row.payload_json),
                ),
            )
            for row in submission_rows
        ),
    )

    review_rows = connection.execute(
        sa.select(
            task_review_decisions.c.id,
            task_review_decisions.c.account_id,
            task_review_decisions.c.task_instance_id,
            task_review_decisions.c.submission_id,
        )
    ).mappings()
    review_account_map = _update_from_map(
        connection,
        table=task_review_decisions,
        id_column=task_review_decisions.c.id,
        updates=(
            (
                row.id,
                _first_valid_account_id(
                    valid_account_ids,
                    row.account_id,
                    instance_account_map.get(row.task_instance_id),
                    submission_account_map.get(row.submission_id),
                ),
            )
            for row in review_rows
        ),
    )

    ticket_rows = connection.execute(
        sa.select(
            tickets.c.id,
            tickets.c.account_id,
            tickets.c.linked_task_instance_id,
            tickets.c.linked_submission_id,
            tickets.c.review_decision_id,
            tickets.c.site_id,
            tickets.c.metadata_json,
        )
    ).mappings()
    _update_from_map(
        connection,
        table=tickets,
        id_column=tickets.c.id,
        updates=(
            (
                row.id,
                _first_valid_account_id(
                    valid_account_ids,
                    row.account_id,
                    instance_account_map.get(row.linked_task_instance_id),
                    submission_account_map.get(row.linked_submission_id),
                    review_account_map.get(row.review_decision_id),
                    site_account_map.get(row.site_id),
                    _extract_account_id(row.metadata_json),
                ),
            )
            for row in ticket_rows
        ),
    )


def _assert_no_null_account_ids() -> None:
    connection = op.get_bind()
    unresolved: dict[str, int] = {}

    for table_name in TARGET_TABLES:
        table = sa.table(
            table_name,
            sa.column("id", sa.String(length=36)),
            sa.column("account_id", sa.String(length=128)),
        )
        unresolved_count = connection.execute(
            sa.select(sa.func.count()).select_from(table).where(table.c.account_id.is_(None))
        ).scalar_one()
        if unresolved_count:
            unresolved[table_name] = int(unresolved_count)

    if unresolved:
        details = ", ".join(f"{table}={count}" for table, count in sorted(unresolved.items()))
        raise RuntimeError(
            "Cannot enforce NOT NULL on task workflow account scope columns; unresolved historical rows remain: "
            f"{details}. Backfill parent H5/task account scope data before rerunning this migration."
        )


def _backfill_from_metadata(
    connection: sa.Connection,
    *,
    table: sa.TableClause,
    id_column: sa.ColumnClause[str],
    json_column: sa.ColumnClause[Any],
    valid_account_ids: set[str],
) -> dict[str, str]:
    rows = connection.execute(sa.select(id_column, table.c.account_id, json_column)).mappings()
    return _update_from_map(
        connection,
        table=table,
        id_column=id_column,
        updates=(
            (
                str(row[id_column.name]),
                _first_valid_account_id(
                    valid_account_ids,
                    row.account_id,
                    _extract_account_id(row[json_column.name]),
                ),
            )
            for row in rows
        ),
    )


def _update_from_map(
    connection: sa.Connection,
    *,
    table: sa.TableClause,
    id_column: sa.ColumnClause[str],
    updates: Iterable[tuple[str, str | None]],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for row_id, account_id in updates:
        if account_id is None:
            continue
        connection.execute(
            table.update().where(id_column == row_id).values(account_id=account_id)
        )
        resolved[row_id] = account_id
    return resolved


def _extract_account_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw_value = payload.get("account_id")
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def _first_valid_account_id(valid_account_ids: set[str], *candidates: str | None) -> str | None:
    for candidate in candidates:
        if candidate is not None and candidate in valid_account_ids:
            return candidate
    return None
