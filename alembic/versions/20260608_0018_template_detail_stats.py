"""add template hourly and failure stats tables

Revision ID: 20260608_0018
Revises: 20260608_0017
Create Date: 2026-06-08 21:10:00
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision = "20260608_0018"
down_revision = "20260608_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_hourly_stats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hour_bucket", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("template_name", sa.String(length=100), nullable=False),
        sa.Column("template_code", sa.String(length=255), nullable=True),
        sa.Column("template_category", sa.String(length=32), nullable=False),
        sa.Column("template_language", sa.String(length=16), nullable=False),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("read_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(12, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["template_id"], ["message_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "date",
            "hour_bucket",
            "account_id",
            "template_id",
            "waba_id",
            "phone_number_id",
            "template_name",
            "template_language",
            name="uq_template_hourly_stats_scope",
        ),
    )
    op.create_index("ix_template_hourly_stats_date", "template_hourly_stats", ["date"])
    op.create_index("ix_template_hourly_stats_hour_bucket", "template_hourly_stats", ["hour_bucket"])
    op.create_index("ix_template_hourly_stats_account_id", "template_hourly_stats", ["account_id"])
    op.create_index("ix_template_hourly_stats_template_id", "template_hourly_stats", ["template_id"])
    op.create_index("ix_template_hourly_stats_waba_id", "template_hourly_stats", ["waba_id"])
    op.create_index(
        "ix_template_hourly_stats_phone_number_id",
        "template_hourly_stats",
        ["phone_number_id"],
    )
    op.create_index(
        "ix_template_hourly_stats_template_name",
        "template_hourly_stats",
        ["template_name"],
    )

    op.create_table(
        "template_failure_stats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("template_name", sa.String(length=100), nullable=False),
        sa.Column("template_code", sa.String(length=255), nullable=True),
        sa.Column("template_category", sa.String(length=32), nullable=False),
        sa.Column("template_language", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["template_id"], ["message_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "date",
            "account_id",
            "template_id",
            "waba_id",
            "phone_number_id",
            "template_name",
            "template_language",
            "error_code",
            name="uq_template_failure_stats_scope",
        ),
    )
    op.create_index("ix_template_failure_stats_date", "template_failure_stats", ["date"])
    op.create_index("ix_template_failure_stats_account_id", "template_failure_stats", ["account_id"])
    op.create_index("ix_template_failure_stats_template_id", "template_failure_stats", ["template_id"])
    op.create_index("ix_template_failure_stats_waba_id", "template_failure_stats", ["waba_id"])
    op.create_index(
        "ix_template_failure_stats_phone_number_id",
        "template_failure_stats",
        ["phone_number_id"],
    )
    op.create_index(
        "ix_template_failure_stats_template_name",
        "template_failure_stats",
        ["template_name"],
    )
    op.create_index(
        "ix_template_failure_stats_error_code",
        "template_failure_stats",
        ["error_code"],
    )

    _backfill_template_detail_stats()


def downgrade() -> None:
    op.drop_index("ix_template_failure_stats_error_code", table_name="template_failure_stats")
    op.drop_index("ix_template_failure_stats_template_name", table_name="template_failure_stats")
    op.drop_index("ix_template_failure_stats_phone_number_id", table_name="template_failure_stats")
    op.drop_index("ix_template_failure_stats_waba_id", table_name="template_failure_stats")
    op.drop_index("ix_template_failure_stats_template_id", table_name="template_failure_stats")
    op.drop_index("ix_template_failure_stats_account_id", table_name="template_failure_stats")
    op.drop_index("ix_template_failure_stats_date", table_name="template_failure_stats")
    op.drop_table("template_failure_stats")

    op.drop_index("ix_template_hourly_stats_template_name", table_name="template_hourly_stats")
    op.drop_index("ix_template_hourly_stats_phone_number_id", table_name="template_hourly_stats")
    op.drop_index("ix_template_hourly_stats_waba_id", table_name="template_hourly_stats")
    op.drop_index("ix_template_hourly_stats_template_id", table_name="template_hourly_stats")
    op.drop_index("ix_template_hourly_stats_account_id", table_name="template_hourly_stats")
    op.drop_index("ix_template_hourly_stats_hour_bucket", table_name="template_hourly_stats")
    op.drop_index("ix_template_hourly_stats_date", table_name="template_hourly_stats")
    op.drop_table("template_hourly_stats")


def _backfill_template_detail_stats() -> None:
    connection = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)

    template_send_logs = sa.table(
        "template_send_logs",
        sa.column("account_id", sa.String()),
        sa.column("template_id", sa.String()),
        sa.column("phone_number_id", sa.String()),
        sa.column("waba_id", sa.String()),
        sa.column("template_name", sa.String()),
        sa.column("template_code", sa.String()),
        sa.column("template_category", sa.String()),
        sa.column("template_language", sa.String()),
        sa.column("status", sa.String()),
        sa.column("error_code", sa.String()),
        sa.column("billable", sa.Boolean()),
        sa.column("estimated_cost", sa.Numeric(12, 4)),
        sa.column("sent_at", sa.DateTime()),
        sa.column("created_at", sa.DateTime()),
        sa.column("delivered_at", sa.DateTime()),
        sa.column("read_at", sa.DateTime()),
        sa.column("failed_at", sa.DateTime()),
        sa.column("last_status_at", sa.DateTime()),
    )
    whatsapp_phone_numbers = sa.table(
        "whatsapp_phone_numbers",
        sa.column("id", sa.String()),
        sa.column("phone_number_id", sa.String()),
    )

    rows = connection.execute(
        sa.select(
            template_send_logs.c.account_id,
            template_send_logs.c.template_id,
            template_send_logs.c.waba_id,
            template_send_logs.c.template_name,
            template_send_logs.c.template_code,
            template_send_logs.c.template_category,
            template_send_logs.c.template_language,
            template_send_logs.c.status,
            template_send_logs.c.error_code,
            template_send_logs.c.billable,
            template_send_logs.c.estimated_cost,
            template_send_logs.c.sent_at,
            template_send_logs.c.created_at,
            template_send_logs.c.delivered_at,
            template_send_logs.c.read_at,
            template_send_logs.c.failed_at,
            template_send_logs.c.last_status_at,
            whatsapp_phone_numbers.c.phone_number_id.label("provider_phone_number_id"),
        ).select_from(
            template_send_logs.outerjoin(
                whatsapp_phone_numbers,
                template_send_logs.c.phone_number_id == whatsapp_phone_numbers.c.id,
            )
        )
    ).mappings()

    hourly_aggregates: dict[
        tuple[object, int, str, str | None, str | None, str | None, str, str | None, str, str],
        dict[str, Decimal | int],
    ] = defaultdict(
        lambda: {
            "send_count": 0,
            "delivered_count": 0,
            "read_count": 0,
            "failed_count": 0,
            "billable_count": 0,
            "estimated_cost": Decimal("0"),
        }
    )
    failure_aggregates: dict[
        tuple[object, str, str | None, str | None, str | None, str, str | None, str, str, str],
        int,
    ] = defaultdict(int)

    for row in rows:
        if not row["template_name"] or not row["template_language"] or not row["template_category"]:
            continue

        occurred_at = (
            row["sent_at"] or row["created_at"] or row["failed_at"] or row["last_status_at"]
        )
        if occurred_at is None:
            continue

        stat_date = occurred_at.date()
        estimated_cost = Decimal(str(row["estimated_cost"] or 0))
        hourly_key = (
            stat_date,
            occurred_at.hour,
            row["account_id"],
            row["template_id"],
            row["waba_id"],
            row["provider_phone_number_id"],
            row["template_name"],
            row["template_code"],
            row["template_category"],
            row["template_language"],
        )
        hourly_aggregates[hourly_key]["send_count"] += 1
        if row["delivered_at"] is not None or row["status"] in {"DELIVERED", "READ"}:
            hourly_aggregates[hourly_key]["delivered_count"] += 1
        if row["read_at"] is not None or row["status"] == "READ":
            hourly_aggregates[hourly_key]["read_count"] += 1
        if row["failed_at"] is not None or row["status"] == "FAILED":
            hourly_aggregates[hourly_key]["failed_count"] += 1
            failure_key = (
                stat_date,
                row["account_id"],
                row["template_id"],
                row["waba_id"],
                row["provider_phone_number_id"],
                row["template_name"],
                row["template_code"],
                row["template_category"],
                row["template_language"],
                row["error_code"] or "unknown",
            )
            failure_aggregates[failure_key] += 1
        if row["billable"]:
            hourly_aggregates[hourly_key]["billable_count"] += 1
        hourly_aggregates[hourly_key]["estimated_cost"] += estimated_cost

    if hourly_aggregates:
        hourly_table = sa.table(
            "template_hourly_stats",
            sa.column("id", sa.String()),
            sa.column("date", sa.Date()),
            sa.column("hour_bucket", sa.Integer()),
            sa.column("account_id", sa.String()),
            sa.column("template_id", sa.String()),
            sa.column("waba_id", sa.String()),
            sa.column("phone_number_id", sa.String()),
            sa.column("template_name", sa.String()),
            sa.column("template_code", sa.String()),
            sa.column("template_category", sa.String()),
            sa.column("template_language", sa.String()),
            sa.column("send_count", sa.Integer()),
            sa.column("delivered_count", sa.Integer()),
            sa.column("read_count", sa.Integer()),
            sa.column("failed_count", sa.Integer()),
            sa.column("billable_count", sa.Integer()),
            sa.column("estimated_cost", sa.Numeric(12, 4)),
            sa.column("created_at", sa.DateTime()),
            sa.column("updated_at", sa.DateTime()),
        )
        op.bulk_insert(
            hourly_table,
            [
                {
                    "id": str(uuid4()),
                    "date": key[0],
                    "hour_bucket": key[1],
                    "account_id": key[2],
                    "template_id": key[3],
                    "waba_id": key[4],
                    "phone_number_id": key[5],
                    "template_name": key[6],
                    "template_code": key[7],
                    "template_category": key[8],
                    "template_language": key[9],
                    "send_count": int(counts["send_count"]),
                    "delivered_count": int(counts["delivered_count"]),
                    "read_count": int(counts["read_count"]),
                    "failed_count": int(counts["failed_count"]),
                    "billable_count": int(counts["billable_count"]),
                    "estimated_cost": counts["estimated_cost"],
                    "created_at": now,
                    "updated_at": now,
                }
                for key, counts in hourly_aggregates.items()
            ],
        )

    if failure_aggregates:
        failure_table = sa.table(
            "template_failure_stats",
            sa.column("id", sa.String()),
            sa.column("date", sa.Date()),
            sa.column("account_id", sa.String()),
            sa.column("template_id", sa.String()),
            sa.column("waba_id", sa.String()),
            sa.column("phone_number_id", sa.String()),
            sa.column("template_name", sa.String()),
            sa.column("template_code", sa.String()),
            sa.column("template_category", sa.String()),
            sa.column("template_language", sa.String()),
            sa.column("error_code", sa.String()),
            sa.column("failed_count", sa.Integer()),
            sa.column("created_at", sa.DateTime()),
            sa.column("updated_at", sa.DateTime()),
        )
        op.bulk_insert(
            failure_table,
            [
                {
                    "id": str(uuid4()),
                    "date": key[0],
                    "account_id": key[1],
                    "template_id": key[2],
                    "waba_id": key[3],
                    "phone_number_id": key[4],
                    "template_name": key[5],
                    "template_code": key[6],
                    "template_category": key[7],
                    "template_language": key[8],
                    "error_code": key[9],
                    "failed_count": failed_count,
                    "created_at": now,
                    "updated_at": now,
                }
                for key, failed_count in failure_aggregates.items()
            ],
        )
