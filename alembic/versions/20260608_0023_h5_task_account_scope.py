"""add account scope columns to h5 task and ticket workflow tables

Revision ID: 20260608_0023
Revises: 20260608_0022
Create Date: 2026-06-08 16:30:00
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from alembic import op


revision = "20260608_0023"
down_revision = "20260608_0022"
branch_labels = None
depends_on = None


ACCOUNT_COLUMN_TABLES: tuple[tuple[str, str, str], ...] = (
    ("h5_sites", "fk_h5_sites_account_id_accounts", "ix_h5_sites_account_id"),
    ("task_templates", "fk_task_templates_account_id_accounts", "ix_task_templates_account_id"),
    ("task_instances", "fk_task_instances_account_id_accounts", "ix_task_instances_account_id"),
    ("task_proof_files", "fk_task_proof_files_account_id_accounts", "ix_task_proof_files_account_id"),
    ("task_submissions", "fk_task_submissions_account_id_accounts", "ix_task_submissions_account_id"),
    ("task_review_decisions", "fk_task_review_decisions_account_id_accounts", "ix_task_review_decisions_account_id"),
    ("tickets", "fk_tickets_account_id_accounts", "ix_tickets_account_id"),
)


def upgrade() -> None:
    for table_name, fk_name, index_name in ACCOUNT_COLUMN_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("account_id", sa.String(length=128), nullable=True))
            batch_op.create_foreign_key(fk_name, "accounts", ["account_id"], ["account_id"])
            batch_op.create_index(index_name, ["account_id"], unique=False)

    _backfill_account_ids()


def downgrade() -> None:
    for table_name, fk_name, index_name in reversed(ACCOUNT_COLUMN_TABLES):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_index(index_name)
            batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.drop_column("account_id")


def _backfill_account_ids() -> None:
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
    task_proof_files = sa.table(
        "task_proof_files",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("task_instance_id", sa.String(length=36)),
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
                    template_account_map.get(row.template_id),
                    site_account_map.get(row.site_id),
                    _extract_account_id(row.metadata_json),
                ),
            )
            for row in instance_rows
        ),
    )

    proof_rows = connection.execute(
        sa.select(
            task_proof_files.c.id,
            task_proof_files.c.task_instance_id,
            task_proof_files.c.site_id,
            task_proof_files.c.metadata_json,
        )
    ).mappings()
    _update_from_map(
        connection,
        table=task_proof_files,
        id_column=task_proof_files.c.id,
        updates=(
            (
                row.id,
                _first_valid_account_id(
                    valid_account_ids,
                    instance_account_map.get(row.task_instance_id),
                    site_account_map.get(row.site_id),
                    _extract_account_id(row.metadata_json),
                ),
            )
            for row in proof_rows
        ),
    )

    submission_rows = connection.execute(
        sa.select(
            task_submissions.c.id,
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


def _backfill_from_metadata(
    connection: sa.Connection,
    *,
    table: sa.TableClause,
    id_column: sa.ColumnClause[str],
    json_column: sa.ColumnClause[Any],
    valid_account_ids: set[str],
) -> dict[str, str]:
    rows = connection.execute(sa.select(id_column, json_column)).mappings()
    return _update_from_map(
        connection,
        table=table,
        id_column=id_column,
        updates=(
            (
                str(row[id_column.name]),
                _first_valid_account_id(valid_account_ids, _extract_account_id(row[json_column.name])),
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
