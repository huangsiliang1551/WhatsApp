"""Harden task/H5 parent scope integrity with composite account bindings.

Revision ID: 20260610_0052
Revises: 20260610_0051
Create Date: 2026-06-10 16:30:00
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op


revision: str = "20260610_0052"
down_revision: str | None = "20260610_0051"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    _backfill_parent_scope_account_ids()
    _assert_parent_scope_account_ids_present()
    _assert_task_h5_scope_integrity()

    with op.batch_alter_table("h5_sites") as batch_op:
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_h5_sites_id_account_scope",
            ["id", "account_id"],
        )

    with op.batch_alter_table("app_users") as batch_op:
        batch_op.drop_constraint("fk_app_users_registration_site_id_h5_sites", type_="foreignkey")
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_app_users_id_account_scope",
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_app_users_registration_site_account_scope",
            "h5_sites",
            ["registration_site_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("task_templates") as batch_op:
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_task_templates_id_account_scope",
            ["id", "account_id"],
        )

    with op.batch_alter_table("task_instances") as batch_op:
        batch_op.drop_constraint("fk_task_instances_template_id_task_templates", type_="foreignkey")
        batch_op.drop_constraint("fk_task_instances_user_id_app_users", type_="foreignkey")
        batch_op.drop_constraint("fk_task_instances_site_id_h5_sites", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_task_instances_template_account_scope",
            "task_templates",
            ["template_id", "account_id"],
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_task_instances_user_account_scope",
            "app_users",
            ["user_id", "account_id"],
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_task_instances_site_account_scope",
            "h5_sites",
            ["site_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("task_proof_files") as batch_op:
        batch_op.drop_constraint("fk_task_proof_files_user_id_app_users", type_="foreignkey")
        batch_op.drop_constraint("fk_task_proof_files_site_id_h5_sites", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_task_proof_files_user_account_scope",
            "app_users",
            ["user_id", "account_id"],
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_task_proof_files_site_account_scope",
            "h5_sites",
            ["site_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("task_submissions") as batch_op:
        batch_op.drop_constraint("fk_task_submissions_submitted_by_user_id_app_users", type_="foreignkey")
        batch_op.drop_constraint("fk_task_submissions_site_id_h5_sites", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_task_submissions_submitted_by_user_account_scope",
            "app_users",
            ["submitted_by_user_id", "account_id"],
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_task_submissions_site_account_scope",
            "h5_sites",
            ["site_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("task_review_decisions") as batch_op:
        batch_op.drop_constraint("fk_task_review_decisions_task_instance_id_task_instances", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_task_review_decisions_task_instance_account_scope",
            "task_instances",
            ["task_instance_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("fk_tickets_linked_task_instance_id_task_instances", type_="foreignkey")
        batch_op.drop_constraint("fk_tickets_user_id_app_users", type_="foreignkey")
        batch_op.drop_constraint("fk_tickets_site_id_h5_sites", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_tickets_task_instance_account_scope",
            "task_instances",
            ["linked_task_instance_id", "account_id"],
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_tickets_user_account_scope",
            "app_users",
            ["user_id", "account_id"],
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_tickets_site_account_scope",
            "h5_sites",
            ["site_id", "account_id"],
            ["id", "account_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("fk_tickets_site_account_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_tickets_user_account_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_tickets_task_instance_account_scope", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_tickets_linked_task_instance_id_task_instances",
            "task_instances",
            ["linked_task_instance_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_tickets_user_id_app_users",
            "app_users",
            ["user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_tickets_site_id_h5_sites",
            "h5_sites",
            ["site_id"],
            ["id"],
        )

    with op.batch_alter_table("task_review_decisions") as batch_op:
        batch_op.drop_constraint("fk_task_review_decisions_task_instance_account_scope", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_task_review_decisions_task_instance_id_task_instances",
            "task_instances",
            ["task_instance_id"],
            ["id"],
        )

    with op.batch_alter_table("task_submissions") as batch_op:
        batch_op.drop_constraint(
            "fk_task_submissions_site_account_scope",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_task_submissions_submitted_by_user_account_scope",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_task_submissions_submitted_by_user_id_app_users",
            "app_users",
            ["submitted_by_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_task_submissions_site_id_h5_sites",
            "h5_sites",
            ["site_id"],
            ["id"],
        )

    with op.batch_alter_table("task_proof_files") as batch_op:
        batch_op.drop_constraint("fk_task_proof_files_site_account_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_task_proof_files_user_account_scope", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_task_proof_files_user_id_app_users",
            "app_users",
            ["user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_task_proof_files_site_id_h5_sites",
            "h5_sites",
            ["site_id"],
            ["id"],
        )

    with op.batch_alter_table("task_instances") as batch_op:
        batch_op.drop_constraint("fk_task_instances_site_account_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_task_instances_user_account_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_task_instances_template_account_scope", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_task_instances_template_id_task_templates",
            "task_templates",
            ["template_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_task_instances_user_id_app_users",
            "app_users",
            ["user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_task_instances_site_id_h5_sites",
            "h5_sites",
            ["site_id"],
            ["id"],
        )

    with op.batch_alter_table("task_templates") as batch_op:
        batch_op.drop_constraint("uq_task_templates_id_account_scope", type_="unique")
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )

    with op.batch_alter_table("app_users") as batch_op:
        batch_op.drop_constraint("fk_app_users_registration_site_account_scope", type_="foreignkey")
        batch_op.drop_constraint("uq_app_users_id_account_scope", type_="unique")
        batch_op.create_foreign_key(
            "fk_app_users_registration_site_id_h5_sites",
            "h5_sites",
            ["registration_site_id"],
            ["id"],
        )
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )

    with op.batch_alter_table("h5_sites") as batch_op:
        batch_op.drop_constraint("uq_h5_sites_id_account_scope", type_="unique")
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )


def _backfill_parent_scope_account_ids() -> None:
    connection = op.get_bind()

    accounts = sa.table("accounts", sa.column("account_id", sa.String(length=128)))
    h5_sites = sa.table(
        "h5_sites",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("metadata_json", sa.JSON()),
    )
    invite_codes = sa.table(
        "invite_codes",
        sa.column("code", sa.String(length=64)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("metadata_json", sa.JSON()),
    )
    app_users = sa.table(
        "app_users",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("registration_site_id", sa.String(length=36)),
        sa.column("registration_invite_code", sa.String(length=64)),
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
        sa.column("user_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("metadata_json", sa.JSON()),
    )
    task_proof_files = sa.table(
        "task_proof_files",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("user_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("metadata_json", sa.JSON()),
    )
    task_submissions = sa.table(
        "task_submissions",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("submitted_by_user_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("payload_json", sa.JSON()),
    )
    tickets = sa.table(
        "tickets",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("user_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("linked_task_instance_id", sa.String(length=36)),
        sa.column("linked_submission_id", sa.String(length=36)),
        sa.column("metadata_json", sa.JSON()),
    )

    valid_account_ids = {
        str(row.account_id)
        for row in connection.execute(sa.select(accounts.c.account_id)).mappings()
        if row.account_id is not None
    }

    site_related_candidates = _collect_related_account_candidates(
        valid_account_ids=valid_account_ids,
        rows=connection.execute(
            sa.select(
                app_users.c.registration_site_id.label("site_id"),
                app_users.c.account_id,
            )
        ).mappings(),
        subject_key="site_id",
        candidate_builder=lambda row: (row.account_id,),
    )
    _merge_related_account_candidates(
        site_related_candidates,
        _collect_related_account_candidates(
            valid_account_ids=valid_account_ids,
            rows=connection.execute(
                sa.select(
                    task_instances.c.site_id,
                    task_instances.c.account_id,
                    task_instances.c.metadata_json,
                )
            ).mappings(),
            subject_key="site_id",
            candidate_builder=lambda row: (
                row.account_id,
                _extract_account_id(row.metadata_json),
            ),
        ),
    )
    _merge_related_account_candidates(
        site_related_candidates,
        _collect_related_account_candidates(
            valid_account_ids=valid_account_ids,
            rows=connection.execute(
                sa.select(
                    task_proof_files.c.site_id,
                    task_proof_files.c.account_id,
                    task_proof_files.c.metadata_json,
                )
            ).mappings(),
            subject_key="site_id",
            candidate_builder=lambda row: (
                row.account_id,
                _extract_account_id(row.metadata_json),
            ),
        ),
    )
    _merge_related_account_candidates(
        site_related_candidates,
        _collect_related_account_candidates(
            valid_account_ids=valid_account_ids,
            rows=connection.execute(
                sa.select(
                    task_submissions.c.site_id,
                    task_submissions.c.account_id,
                    task_submissions.c.payload_json,
                )
            ).mappings(),
            subject_key="site_id",
            candidate_builder=lambda row: (
                row.account_id,
                _extract_account_id(row.payload_json),
            ),
        ),
    )
    _merge_related_account_candidates(
        site_related_candidates,
        _collect_related_account_candidates(
            valid_account_ids=valid_account_ids,
            rows=connection.execute(
                sa.select(
                    tickets.c.site_id,
                    tickets.c.account_id,
                    tickets.c.metadata_json,
                )
            ).mappings(),
            subject_key="site_id",
            candidate_builder=lambda row: (
                row.account_id,
                _extract_account_id(row.metadata_json),
            ),
        ),
    )

    site_rows = connection.execute(
        sa.select(
            h5_sites.c.id,
            h5_sites.c.account_id,
            h5_sites.c.metadata_json,
        )
    ).mappings()
    site_account_map: dict[str, str] = {}
    for row in site_rows:
        resolved_account_id = _resolve_single_account_id(
            valid_account_ids,
            row.account_id,
            _extract_account_id(row.metadata_json),
            *sorted(site_related_candidates.get(str(row.id), set())),
        )
        if resolved_account_id is None:
            continue
        connection.execute(
            h5_sites.update().where(h5_sites.c.id == row.id).values(account_id=resolved_account_id)
        )
        site_account_map[str(row.id)] = resolved_account_id

    template_related_candidates = _collect_related_account_candidates(
        valid_account_ids=valid_account_ids,
        rows=connection.execute(
            sa.select(
                task_instances.c.template_id,
                task_instances.c.account_id,
                task_instances.c.metadata_json,
            )
        ).mappings(),
        subject_key="template_id",
        candidate_builder=lambda row: (
            row.account_id,
            _extract_account_id(row.metadata_json),
        ),
    )
    template_rows = connection.execute(
        sa.select(
            task_templates.c.id,
            task_templates.c.account_id,
            task_templates.c.metadata_json,
        )
    ).mappings()
    template_account_map: dict[str, str] = {}
    for row in template_rows:
        resolved_account_id = _resolve_single_account_id(
            valid_account_ids,
            row.account_id,
            _extract_account_id(row.metadata_json),
            *sorted(template_related_candidates.get(str(row.id), set())),
        )
        if resolved_account_id is None:
            continue
        connection.execute(
            task_templates.update().where(task_templates.c.id == row.id).values(account_id=resolved_account_id)
        )
        template_account_map[str(row.id)] = resolved_account_id

    invite_code_account_map = _build_direct_account_map(
        rows=connection.execute(
            sa.select(invite_codes.c.code, invite_codes.c.site_id, invite_codes.c.metadata_json)
        ).mappings(),
        id_key="code",
        valid_account_ids=valid_account_ids,
        candidate_builder=lambda row: (
            site_account_map.get(str(row.site_id)) if row.site_id is not None else None,
            _extract_account_id(row.metadata_json),
        ),
    )

    instance_account_map = _build_direct_account_map(
        rows=connection.execute(
            sa.select(
                task_instances.c.id,
                task_instances.c.account_id,
                task_instances.c.template_id,
                task_instances.c.site_id,
                task_instances.c.metadata_json,
            )
        ).mappings(),
        id_key="id",
        valid_account_ids=valid_account_ids,
        candidate_builder=lambda row: (
            row.account_id,
            template_account_map.get(str(row.template_id)) if row.template_id is not None else None,
            site_account_map.get(str(row.site_id)) if row.site_id is not None else None,
            _extract_account_id(row.metadata_json),
        ),
    )
    submission_account_map = _build_direct_account_map(
        rows=connection.execute(
            sa.select(
                task_submissions.c.id,
                task_submissions.c.account_id,
                task_submissions.c.task_instance_id,
                task_submissions.c.site_id,
                task_submissions.c.payload_json,
            )
        ).mappings(),
        id_key="id",
        valid_account_ids=valid_account_ids,
        candidate_builder=lambda row: (
            row.account_id,
            instance_account_map.get(str(row.task_instance_id)) if row.task_instance_id is not None else None,
            site_account_map.get(str(row.site_id)) if row.site_id is not None else None,
            _extract_account_id(row.payload_json),
        ),
    )

    user_related_candidates = _collect_related_account_candidates(
        valid_account_ids=valid_account_ids,
        rows=connection.execute(
            sa.select(
                task_instances.c.user_id,
                task_instances.c.account_id,
                task_instances.c.template_id,
                task_instances.c.site_id,
                task_instances.c.metadata_json,
            )
        ).mappings(),
        subject_key="user_id",
        candidate_builder=lambda row: (
            row.account_id,
            template_account_map.get(str(row.template_id)) if row.template_id is not None else None,
            site_account_map.get(str(row.site_id)) if row.site_id is not None else None,
            _extract_account_id(row.metadata_json),
        ),
    )
    _merge_related_account_candidates(
        user_related_candidates,
        _collect_related_account_candidates(
            valid_account_ids=valid_account_ids,
            rows=connection.execute(
                sa.select(
                    task_proof_files.c.user_id,
                    task_proof_files.c.account_id,
                    task_proof_files.c.task_instance_id,
                    task_proof_files.c.site_id,
                    task_proof_files.c.metadata_json,
                )
            ).mappings(),
            subject_key="user_id",
            candidate_builder=lambda row: (
                row.account_id,
                instance_account_map.get(str(row.task_instance_id)) if row.task_instance_id is not None else None,
                site_account_map.get(str(row.site_id)) if row.site_id is not None else None,
                _extract_account_id(row.metadata_json),
            ),
        ),
    )
    _merge_related_account_candidates(
        user_related_candidates,
        _collect_related_account_candidates(
            valid_account_ids=valid_account_ids,
            rows=connection.execute(
                sa.select(
                    task_submissions.c.submitted_by_user_id.label("user_id"),
                    task_submissions.c.account_id,
                    task_submissions.c.task_instance_id,
                    task_submissions.c.site_id,
                    task_submissions.c.payload_json,
                )
            ).mappings(),
            subject_key="user_id",
            candidate_builder=lambda row: (
                row.account_id,
                instance_account_map.get(str(row.task_instance_id)) if row.task_instance_id is not None else None,
                site_account_map.get(str(row.site_id)) if row.site_id is not None else None,
                _extract_account_id(row.payload_json),
            ),
        ),
    )
    _merge_related_account_candidates(
        user_related_candidates,
        _collect_related_account_candidates(
            valid_account_ids=valid_account_ids,
            rows=connection.execute(
                sa.select(
                    tickets.c.user_id,
                    tickets.c.account_id,
                    tickets.c.linked_task_instance_id,
                    tickets.c.linked_submission_id,
                    tickets.c.site_id,
                    tickets.c.metadata_json,
                )
            ).mappings(),
            subject_key="user_id",
            candidate_builder=lambda row: (
                row.account_id,
                instance_account_map.get(str(row.linked_task_instance_id))
                if row.linked_task_instance_id is not None
                else None,
                submission_account_map.get(str(row.linked_submission_id))
                if row.linked_submission_id is not None
                else None,
                site_account_map.get(str(row.site_id)) if row.site_id is not None else None,
                _extract_account_id(row.metadata_json),
            ),
        ),
    )

    user_rows = connection.execute(
        sa.select(
            app_users.c.id,
            app_users.c.account_id,
            app_users.c.registration_site_id,
            app_users.c.registration_invite_code,
        )
    ).mappings()
    for row in user_rows:
        resolved_account_id = _resolve_single_account_id(
            valid_account_ids,
            row.account_id,
            site_account_map.get(str(row.registration_site_id)) if row.registration_site_id is not None else None,
            invite_code_account_map.get(str(row.registration_invite_code))
            if row.registration_invite_code is not None
            else None,
            *sorted(user_related_candidates.get(str(row.id), set())),
        )
        if resolved_account_id is None:
            continue
        connection.execute(
            app_users.update().where(app_users.c.id == row.id).values(account_id=resolved_account_id)
        )


def _assert_parent_scope_account_ids_present() -> None:
    connection = op.get_bind()
    unresolved: dict[str, int] = {}

    for table_name in ("h5_sites", "app_users", "task_templates"):
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
            "Cannot harden task/H5 parent account scope; unresolved parent rows remain: "
            f"{details}. Backfill parent account_id values before rerunning this migration."
        )


def _assert_task_h5_scope_integrity() -> None:
    connection = op.get_bind()

    checks = (
        (
            "app user registration site",
            """
            SELECT app_user.id
            FROM app_users AS app_user
            JOIN h5_sites AS site ON site.id = app_user.registration_site_id
            WHERE app_user.registration_site_id IS NOT NULL
              AND (app_user.account_id != site.account_id)
            ORDER BY app_user.id
            LIMIT 5
            """,
        ),
        (
            "task instance template",
            """
            SELECT task.id
            FROM task_instances AS task
            JOIN task_templates AS template ON template.id = task.template_id
            WHERE task.account_id != template.account_id
            ORDER BY task.id
            LIMIT 5
            """,
        ),
        (
            "task instance user",
            """
            SELECT task.id
            FROM task_instances AS task
            JOIN app_users AS app_user ON app_user.id = task.user_id
            WHERE task.account_id != app_user.account_id
            ORDER BY task.id
            LIMIT 5
            """,
        ),
        (
            "task instance site",
            """
            SELECT task.id
            FROM task_instances AS task
            JOIN h5_sites AS site ON site.id = task.site_id
            WHERE task.site_id IS NOT NULL
              AND task.account_id != site.account_id
            ORDER BY task.id
            LIMIT 5
            """,
        ),
        (
            "task proof file user",
            """
            SELECT proof.id
            FROM task_proof_files AS proof
            JOIN app_users AS app_user ON app_user.id = proof.user_id
            WHERE proof.account_id != app_user.account_id
            ORDER BY proof.id
            LIMIT 5
            """,
        ),
        (
            "task proof file site",
            """
            SELECT proof.id
            FROM task_proof_files AS proof
            JOIN h5_sites AS site ON site.id = proof.site_id
            WHERE proof.site_id IS NOT NULL
              AND proof.account_id != site.account_id
            ORDER BY proof.id
            LIMIT 5
            """,
        ),
        (
            "task submission user",
            """
            SELECT submission.id
            FROM task_submissions AS submission
            JOIN app_users AS app_user ON app_user.id = submission.submitted_by_user_id
            WHERE submission.account_id != app_user.account_id
            ORDER BY submission.id
            LIMIT 5
            """,
        ),
        (
            "task submission site",
            """
            SELECT submission.id
            FROM task_submissions AS submission
            JOIN h5_sites AS site ON site.id = submission.site_id
            WHERE submission.site_id IS NOT NULL
              AND submission.account_id != site.account_id
            ORDER BY submission.id
            LIMIT 5
            """,
        ),
        (
            "ticket task instance",
            """
            SELECT ticket.id
            FROM tickets AS ticket
            JOIN task_instances AS task ON task.id = ticket.linked_task_instance_id
            WHERE ticket.linked_task_instance_id IS NOT NULL
              AND ticket.account_id != task.account_id
            ORDER BY ticket.id
            LIMIT 5
            """,
        ),
        (
            "ticket user",
            """
            SELECT ticket.id
            FROM tickets AS ticket
            JOIN app_users AS app_user ON app_user.id = ticket.user_id
            WHERE ticket.account_id != app_user.account_id
            ORDER BY ticket.id
            LIMIT 5
            """,
        ),
        (
            "ticket site",
            """
            SELECT ticket.id
            FROM tickets AS ticket
            JOIN h5_sites AS site ON site.id = ticket.site_id
            WHERE ticket.site_id IS NOT NULL
              AND ticket.account_id != site.account_id
            ORDER BY ticket.id
            LIMIT 5
            """,
        ),
    )

    for label, sql in checks:
        rows = connection.execute(sa.text(sql)).fetchall()
        if rows:
            sample_ids = ", ".join(str(row[0]) for row in rows)
            raise RuntimeError(
                f"Cannot harden task/H5 scope for {label}; cross-account links remain for: {sample_ids}."
            )


def _build_direct_account_map(
    *,
    rows: Iterable[Mapping[str, Any]],
    id_key: str,
    valid_account_ids: set[str],
    candidate_builder: Callable[[Mapping[str, Any]], Iterable[str | None]],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for row in rows:
        row_id = row.get(id_key)
        if row_id is None:
            continue
        account_id = _resolve_single_account_id(valid_account_ids, *candidate_builder(row))
        if account_id is not None:
            resolved[str(row_id)] = account_id
    return resolved


def _collect_related_account_candidates(
    *,
    valid_account_ids: set[str],
    rows: Iterable[Mapping[str, Any]],
    subject_key: str,
    candidate_builder: Callable[[Mapping[str, Any]], Iterable[str | None]],
) -> dict[str, set[str]]:
    resolved: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        raw_subject_id = row.get(subject_key)
        if raw_subject_id is None:
            continue
        subject_id = str(raw_subject_id)
        for candidate in candidate_builder(row):
            if candidate is not None and candidate in valid_account_ids:
                resolved[subject_id].add(candidate)
    return resolved


def _merge_related_account_candidates(
    target: dict[str, set[str]],
    source: dict[str, set[str]],
) -> None:
    for subject_id, account_ids in source.items():
        target.setdefault(subject_id, set()).update(account_ids)


def _resolve_single_account_id(
    valid_account_ids: set[str],
    *candidates: str | None,
) -> str | None:
    unique_candidates = {
        candidate
        for candidate in candidates
        if candidate is not None and candidate in valid_account_ids
    }
    if len(unique_candidates) != 1:
        return None
    return next(iter(unique_candidates))


def _extract_account_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw_value = payload.get("account_id")
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None
