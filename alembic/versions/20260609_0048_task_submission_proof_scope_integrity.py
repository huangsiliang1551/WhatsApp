"""enforce task submission proof task/account scope integrity

Revision ID: 20260609_0048
Revises: 20260609_0047
Create Date: 2026-06-10 00:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260609_0048"
down_revision = "20260609_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "task_submission_proofs",
        sa.Column("account_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "task_submission_proofs",
        sa.Column("task_instance_id", sa.String(length=36), nullable=True),
    )

    _backfill_task_submission_proof_scope()
    _assert_task_submission_proof_scope_integrity()

    with op.batch_alter_table("task_proof_files") as batch_op:
        batch_op.create_unique_constraint(
            "uq_task_proof_files_id_task_instance_account_scope",
            ["id", "task_instance_id", "account_id"],
        )

    with op.batch_alter_table("task_submission_proofs") as batch_op:
        batch_op.drop_constraint(
            "fk_task_submission_proofs_submission_id_task_submissions",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_task_submission_proofs_proof_file_id_task_proof_files",
            type_="foreignkey",
        )
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.alter_column(
            "task_instance_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_task_submission_proofs_account_id_accounts",
            "accounts",
            ["account_id"],
            ["account_id"],
        )
        batch_op.create_foreign_key(
            "fk_task_submission_proofs_submission_account_scope",
            "task_submissions",
            ["submission_id", "task_instance_id", "account_id"],
            ["id", "task_instance_id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_task_submission_proofs_proof_file_account_scope",
            "task_proof_files",
            ["proof_file_id", "task_instance_id", "account_id"],
            ["id", "task_instance_id", "account_id"],
        )
        batch_op.create_index("ix_task_submission_proofs_account_id", ["account_id"])
        batch_op.create_index("ix_task_submission_proofs_task_instance_id", ["task_instance_id"])


def downgrade() -> None:
    with op.batch_alter_table("task_submission_proofs") as batch_op:
        batch_op.drop_index("ix_task_submission_proofs_task_instance_id")
        batch_op.drop_index("ix_task_submission_proofs_account_id")
        batch_op.drop_constraint(
            "fk_task_submission_proofs_proof_file_account_scope",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_task_submission_proofs_submission_account_scope",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_task_submission_proofs_account_id_accounts",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_task_submission_proofs_submission_id_task_submissions",
            "task_submissions",
            ["submission_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_task_submission_proofs_proof_file_id_task_proof_files",
            "task_proof_files",
            ["proof_file_id"],
            ["id"],
        )
        batch_op.drop_column("task_instance_id")
        batch_op.drop_column("account_id")

    with op.batch_alter_table("task_proof_files") as batch_op:
        batch_op.drop_constraint(
            "uq_task_proof_files_id_task_instance_account_scope",
            type_="unique",
        )


def _backfill_task_submission_proof_scope() -> None:
    connection = op.get_bind()

    task_submission_proofs = sa.table(
        "task_submission_proofs",
        sa.column("id", sa.String(length=36)),
        sa.column("submission_id", sa.String(length=36)),
        sa.column("proof_file_id", sa.String(length=36)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
    )
    task_submissions = sa.table(
        "task_submissions",
        sa.column("id", sa.String(length=36)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
    )

    rows = connection.execute(
        sa.select(
            task_submission_proofs.c.id,
            task_submissions.c.task_instance_id,
            task_submissions.c.account_id,
        ).select_from(
            task_submission_proofs.join(
                task_submissions,
                task_submission_proofs.c.submission_id == task_submissions.c.id,
            )
        )
    ).mappings()

    for row in rows:
        connection.execute(
            task_submission_proofs.update()
            .where(task_submission_proofs.c.id == row.id)
            .values(
                task_instance_id=row.task_instance_id,
                account_id=row.account_id,
            )
        )


def _assert_task_submission_proof_scope_integrity() -> None:
    connection = op.get_bind()

    task_submission_proofs = sa.table(
        "task_submission_proofs",
        sa.column("id", sa.String(length=36)),
        sa.column("submission_id", sa.String(length=36)),
        sa.column("proof_file_id", sa.String(length=36)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
    )
    task_submissions = sa.table(
        "task_submissions",
        sa.column("id", sa.String(length=36)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
    )
    task_proof_files = sa.table(
        "task_proof_files",
        sa.column("id", sa.String(length=36)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
    )

    rows = connection.execute(
        sa.select(
            task_submission_proofs.c.id,
            task_submission_proofs.c.task_instance_id,
            task_submission_proofs.c.account_id,
            task_submissions.c.task_instance_id.label("submission_task_instance_id"),
            task_submissions.c.account_id.label("submission_account_id"),
            task_proof_files.c.task_instance_id.label("proof_task_instance_id"),
            task_proof_files.c.account_id.label("proof_account_id"),
        ).select_from(
            task_submission_proofs.join(
                task_submissions,
                task_submission_proofs.c.submission_id == task_submissions.c.id,
            ).join(
                task_proof_files,
                task_submission_proofs.c.proof_file_id == task_proof_files.c.id,
            )
        )
    ).mappings()

    for row in rows:
        if (
            row.task_instance_id is None
            or row.account_id is None
            or row.task_instance_id != row.submission_task_instance_id
            or row.account_id != row.submission_account_id
            or row.task_instance_id != row.proof_task_instance_id
            or row.account_id != row.proof_account_id
        ):
            raise RuntimeError(
                "task_submission_proofs contains cross-scope submission/proof links and cannot be upgraded safely."
            )
