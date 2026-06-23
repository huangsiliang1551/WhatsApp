"""tighten task workflow chain integrity constraints

Revision ID: 20260609_0046
Revises: 20260609_0045
Create Date: 2026-06-09 23:40:00
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from alembic import op


revision = "20260609_0046"
down_revision = "20260609_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _backfill_parent_task_scope_account_ids()
    _assert_parent_task_scope_account_ids_present()
    _assert_task_workflow_linkage_integrity()

    with op.batch_alter_table("task_instances") as batch_op:
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_task_instances_id_account_scope",
            ["id", "account_id"],
        )

    with op.batch_alter_table("task_proof_files") as batch_op:
        batch_op.drop_constraint("fk_task_proof_files_task_instance_id_task_instances", type_="foreignkey")
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_task_proof_files_task_instance_account_scope",
            "task_instances",
            ["task_instance_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("task_submissions") as batch_op:
        batch_op.drop_constraint("fk_task_submissions_task_instance_id_task_instances", type_="foreignkey")
        batch_op.create_unique_constraint(
            "uq_task_submissions_id_instance_account_scope",
            ["id", "task_instance_id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_task_submissions_task_instance_account_scope",
            "task_instances",
            ["task_instance_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("task_review_decisions") as batch_op:
        batch_op.drop_constraint("fk_task_review_decisions_submission_id_task_submissions", type_="foreignkey")
        batch_op.create_unique_constraint(
            "uq_task_review_decisions_id_submission_account_scope",
            ["id", "task_instance_id", "submission_id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_task_review_decisions_submission_account_scope",
            "task_submissions",
            ["submission_id", "task_instance_id", "account_id"],
            ["id", "task_instance_id", "account_id"],
        )

    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("fk_tickets_linked_submission_id_task_submissions", type_="foreignkey")
        batch_op.drop_constraint("fk_tickets_review_decision_id_task_review_decisions", type_="foreignkey")
        batch_op.create_check_constraint(
            "ck_tickets_linked_submission_requires_task",
            "linked_submission_id IS NULL OR linked_task_instance_id IS NOT NULL",
        )
        batch_op.create_check_constraint(
            "ck_tickets_review_decision_requires_submission",
            "review_decision_id IS NULL OR (linked_submission_id IS NOT NULL AND linked_task_instance_id IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_tickets_appeal_requires_review_chain",
            "ticket_type != 'appeal' OR (linked_task_instance_id IS NOT NULL AND linked_submission_id IS NOT NULL AND review_decision_id IS NOT NULL)",
        )
        batch_op.create_foreign_key(
            "fk_tickets_submission_account_scope",
            "task_submissions",
            ["linked_submission_id", "linked_task_instance_id", "account_id"],
            ["id", "task_instance_id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_tickets_review_decision_account_scope",
            "task_review_decisions",
            ["review_decision_id", "linked_task_instance_id", "linked_submission_id", "account_id"],
            ["id", "task_instance_id", "submission_id", "account_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("fk_tickets_review_decision_account_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_tickets_submission_account_scope", type_="foreignkey")
        batch_op.drop_constraint("ck_tickets_appeal_requires_review_chain", type_="check")
        batch_op.drop_constraint("ck_tickets_review_decision_requires_submission", type_="check")
        batch_op.drop_constraint("ck_tickets_linked_submission_requires_task", type_="check")
        batch_op.create_foreign_key(
            "fk_tickets_linked_submission_id_task_submissions",
            "task_submissions",
            ["linked_submission_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_tickets_review_decision_id_task_review_decisions",
            "task_review_decisions",
            ["review_decision_id"],
            ["id"],
        )

    with op.batch_alter_table("task_review_decisions") as batch_op:
        batch_op.drop_constraint("fk_task_review_decisions_submission_account_scope", type_="foreignkey")
        batch_op.drop_constraint("uq_task_review_decisions_id_submission_account_scope", type_="unique")
        batch_op.create_foreign_key(
            "fk_task_review_decisions_submission_id_task_submissions",
            "task_submissions",
            ["submission_id"],
            ["id"],
        )

    with op.batch_alter_table("task_submissions") as batch_op:
        batch_op.drop_constraint("fk_task_submissions_task_instance_account_scope", type_="foreignkey")
        batch_op.drop_constraint("uq_task_submissions_id_instance_account_scope", type_="unique")
        batch_op.create_foreign_key(
            "fk_task_submissions_task_instance_id_task_instances",
            "task_instances",
            ["task_instance_id"],
            ["id"],
        )

    with op.batch_alter_table("task_proof_files") as batch_op:
        batch_op.drop_constraint("fk_task_proof_files_task_instance_account_scope", type_="foreignkey")
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_task_proof_files_task_instance_id_task_instances",
            "task_instances",
            ["task_instance_id"],
            ["id"],
        )

    with op.batch_alter_table("task_instances") as batch_op:
        batch_op.drop_constraint("uq_task_instances_id_account_scope", type_="unique")
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )


def _backfill_parent_task_scope_account_ids() -> None:
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
    proof_rows = connection.execute(
        sa.select(
            task_proof_files.c.id,
            task_proof_files.c.account_id,
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
                    row.account_id,
                    instance_account_map.get(row.task_instance_id),
                    site_account_map.get(row.site_id),
                    _extract_account_id(row.metadata_json),
                ),
            )
            for row in proof_rows
        ),
    )


def _assert_parent_task_scope_account_ids_present() -> None:
    connection = op.get_bind()
    for table_name in ("task_instances", "task_proof_files"):
        missing = connection.execute(
            sa.text(f"SELECT id FROM {table_name} WHERE account_id IS NULL ORDER BY id LIMIT 5")
        ).fetchall()
        if missing:
            sample_ids = ", ".join(str(row[0]) for row in missing)
            raise RuntimeError(
                f"Cannot tighten {table_name}.account_id to NOT NULL; sample rows still missing account scope: {sample_ids}."
            )


def _assert_task_workflow_linkage_integrity() -> None:
    connection = op.get_bind()

    review_mismatches = connection.execute(
        sa.text(
            """
            SELECT decision.id
            FROM task_review_decisions AS decision
            JOIN task_submissions AS submission ON submission.id = decision.submission_id
            WHERE decision.task_instance_id != submission.task_instance_id
               OR decision.account_id != submission.account_id
            ORDER BY decision.id
            LIMIT 5
            """
        )
    ).fetchall()
    if review_mismatches:
        sample_ids = ", ".join(str(row[0]) for row in review_mismatches)
        raise RuntimeError(
            "Cannot add task review decision linkage constraints; mismatched submission scope remains for: "
            f"{sample_ids}."
        )

    ticket_submission_mismatches = connection.execute(
        sa.text(
            """
            SELECT ticket.id
            FROM tickets AS ticket
            JOIN task_submissions AS submission ON submission.id = ticket.linked_submission_id
            WHERE ticket.linked_task_instance_id IS NULL
               OR ticket.linked_task_instance_id != submission.task_instance_id
               OR ticket.account_id != submission.account_id
            ORDER BY ticket.id
            LIMIT 5
            """
        )
    ).fetchall()
    if ticket_submission_mismatches:
        sample_ids = ", ".join(str(row[0]) for row in ticket_submission_mismatches)
        raise RuntimeError(
            "Cannot add ticket submission linkage constraints; mismatched linked submission scope remains for: "
            f"{sample_ids}."
        )

    ticket_review_mismatches = connection.execute(
        sa.text(
            """
            SELECT ticket.id
            FROM tickets AS ticket
            JOIN task_review_decisions AS decision ON decision.id = ticket.review_decision_id
            WHERE ticket.linked_task_instance_id IS NULL
               OR ticket.linked_submission_id IS NULL
               OR ticket.linked_task_instance_id != decision.task_instance_id
               OR ticket.linked_submission_id != decision.submission_id
               OR ticket.account_id != decision.account_id
            ORDER BY ticket.id
            LIMIT 5
            """
        )
    ).fetchall()
    if ticket_review_mismatches:
        sample_ids = ", ".join(str(row[0]) for row in ticket_review_mismatches)
        raise RuntimeError(
            "Cannot add ticket review decision linkage constraints; mismatched review chain remains for: "
            f"{sample_ids}."
        )

    invalid_appeals = connection.execute(
        sa.text(
            """
            SELECT id
            FROM tickets
            WHERE ticket_type = 'appeal'
              AND (
                linked_task_instance_id IS NULL
                OR linked_submission_id IS NULL
                OR review_decision_id IS NULL
              )
            ORDER BY id
            LIMIT 5
            """
        )
    ).fetchall()
    if invalid_appeals:
        sample_ids = ", ".join(str(row[0]) for row in invalid_appeals)
        raise RuntimeError(
            "Cannot require appeal review-chain anchors; appeal tickets still missing linked task/submission/review decision: "
            f"{sample_ids}."
        )


def _backfill_from_metadata(
    connection: sa.Connection,
    *,
    table: sa.Table,
    id_column: sa.Column[Any],
    json_column: sa.Column[Any],
    valid_account_ids: set[str],
) -> dict[str, str | None]:
    rows = connection.execute(sa.select(id_column, table.c.account_id, json_column)).mappings()
    return _update_from_map(
        connection,
        table=table,
        id_column=id_column,
        updates=(
            (
                row[id_column.name],
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
    table: sa.Table,
    id_column: sa.Column[Any],
    updates: Iterable[tuple[str, str | None]],
) -> dict[str, str | None]:
    resolved: dict[str, str | None] = {}
    for row_id, account_id in updates:
        if row_id is None:
            continue
        resolved[str(row_id)] = account_id
        if account_id is None:
            continue
        connection.execute(
            table.update()
            .where(id_column == row_id)
            .values(account_id=account_id)
        )
    return resolved


def _extract_account_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("account_id")
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
    return None


def _first_valid_account_id(valid_account_ids: set[str], *candidates: Any) -> str | None:
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        normalized = candidate.strip()
        if normalized and normalized in valid_account_ids:
            return normalized
    return None
