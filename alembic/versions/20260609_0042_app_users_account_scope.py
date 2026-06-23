"""add explicit account scope column to app_users

Revision ID: 20260609_0042
Revises: 20260609_0041
Create Date: 2026-06-09 14:10:00
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any

import sqlalchemy as sa
from alembic import op


revision = "20260609_0042"
down_revision = "20260609_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("app_users") as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.String(length=128), nullable=True))
        batch_op.create_foreign_key(
            "fk_app_users_account_id_accounts",
            "accounts",
            ["account_id"],
            ["account_id"],
        )
        batch_op.create_index("ix_app_users_account_id", ["account_id"], unique=False)

    _backfill_app_user_account_ids()


def downgrade() -> None:
    with op.batch_alter_table("app_users") as batch_op:
        batch_op.drop_index("ix_app_users_account_id")
        batch_op.drop_constraint("fk_app_users_account_id_accounts", type_="foreignkey")
        batch_op.drop_column("account_id")


def _backfill_app_user_account_ids() -> None:
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
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("user_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("metadata_json", sa.JSON()),
    )
    task_submissions = sa.table(
        "task_submissions",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("task_instance_id", sa.String(length=36)),
        sa.column("submitted_by_user_id", sa.String(length=36)),
        sa.column("site_id", sa.String(length=36)),
        sa.column("payload_json", sa.JSON()),
    )
    tickets = sa.table(
        "tickets",
        sa.column("id", sa.String(length=36)),
        sa.column("account_id", sa.String(length=128)),
        sa.column("user_id", sa.String(length=36)),
        sa.column("linked_task_instance_id", sa.String(length=36)),
        sa.column("linked_submission_id", sa.String(length=36)),
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

    valid_account_ids = {
        str(row.account_id)
        for row in connection.execute(sa.select(accounts.c.account_id)).mappings()
        if row.account_id is not None
    }

    site_account_map = _build_direct_account_map(
        rows=connection.execute(
            sa.select(h5_sites.c.id, h5_sites.c.account_id, h5_sites.c.metadata_json)
        ).mappings(),
        id_key="id",
        valid_account_ids=valid_account_ids,
        candidate_builder=lambda row: (row.account_id, _extract_account_id(row.metadata_json)),
    )
    invite_code_account_map = _build_direct_account_map(
        rows=connection.execute(
            sa.select(invite_codes.c.code, invite_codes.c.site_id, invite_codes.c.metadata_json)
        ).mappings(),
        id_key="code",
        valid_account_ids=valid_account_ids,
        candidate_builder=lambda row: (
            site_account_map.get(row.site_id),
            _extract_account_id(row.metadata_json),
        ),
    )
    template_account_map = _build_direct_account_map(
        rows=connection.execute(
            sa.select(task_templates.c.id, task_templates.c.account_id, task_templates.c.metadata_json)
        ).mappings(),
        id_key="id",
        valid_account_ids=valid_account_ids,
        candidate_builder=lambda row: (row.account_id, _extract_account_id(row.metadata_json)),
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
            template_account_map.get(row.template_id),
            site_account_map.get(row.site_id),
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
            instance_account_map.get(row.task_instance_id),
            site_account_map.get(row.site_id),
            _extract_account_id(row.payload_json),
        ),
    )

    related_account_candidates = _collect_related_account_candidates(
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
        user_id_key="user_id",
        candidate_builder=lambda row: (
            row.account_id,
            template_account_map.get(row.template_id),
            site_account_map.get(row.site_id),
            _extract_account_id(row.metadata_json),
        ),
    )
    _merge_related_account_candidates(
        related_account_candidates,
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
            user_id_key="user_id",
            candidate_builder=lambda row: (
                row.account_id,
                instance_account_map.get(row.task_instance_id),
                site_account_map.get(row.site_id),
                _extract_account_id(row.metadata_json),
            ),
        ),
    )
    _merge_related_account_candidates(
        related_account_candidates,
        _collect_related_account_candidates(
            valid_account_ids=valid_account_ids,
            rows=connection.execute(
                sa.select(
                    task_submissions.c.submitted_by_user_id,
                    task_submissions.c.account_id,
                    task_submissions.c.task_instance_id,
                    task_submissions.c.site_id,
                    task_submissions.c.payload_json,
                )
            ).mappings(),
            user_id_key="submitted_by_user_id",
            candidate_builder=lambda row: (
                row.account_id,
                instance_account_map.get(row.task_instance_id),
                site_account_map.get(row.site_id),
                _extract_account_id(row.payload_json),
            ),
        ),
    )
    _merge_related_account_candidates(
        related_account_candidates,
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
            user_id_key="user_id",
            candidate_builder=lambda row: (
                row.account_id,
                instance_account_map.get(row.linked_task_instance_id),
                submission_account_map.get(row.linked_submission_id),
                site_account_map.get(row.site_id),
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
            site_account_map.get(row.registration_site_id),
            invite_code_account_map.get(row.registration_invite_code),
            *sorted(related_account_candidates.get(str(row.id), set())),
        )
        if resolved_account_id is None:
            continue
        connection.execute(
            app_users.update().where(app_users.c.id == row.id).values(account_id=resolved_account_id)
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
    user_id_key: str,
    candidate_builder: Callable[[Mapping[str, Any]], Iterable[str | None]],
) -> dict[str, set[str]]:
    resolved: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        raw_user_id = row.get(user_id_key)
        if raw_user_id is None:
            continue
        user_id = str(raw_user_id)
        for candidate in candidate_builder(row):
            if candidate is not None and candidate in valid_account_ids:
                resolved[user_id].add(candidate)
    return resolved


def _merge_related_account_candidates(
    target: dict[str, set[str]],
    source: dict[str, set[str]],
) -> None:
    for user_id, account_ids in source.items():
        target.setdefault(user_id, set()).update(account_ids)


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
