"""add task template and task instance skeleton tables

Revision ID: 20260608_0020
Revises: 20260608_0019
Create Date: 2026-06-08 23:55:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0020"
down_revision = "20260608_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(length=32), nullable=False, server_default="shopping"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("audience_rule_set_id", sa.String(length=36), nullable=True),
        sa.Column("reward_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("reward_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claim_timeout_seconds", sa.Integer(), nullable=False, server_default="86400"),
        sa.Column("auto_review_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["audience_rule_set_id"], ["audience_rule_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_key"),
    )
    op.create_index("ix_task_templates_task_key", "task_templates", ["task_key"])
    op.create_index("ix_task_templates_audience_rule_set_id", "task_templates", ["audience_rule_set_id"])

    op.create_table(
        "task_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="available"),
        sa.Column("claim_timeout_seconds_snapshot", sa.Integer(), nullable=False, server_default="86400"),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("available_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("claim_deadline_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["task_templates.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_instances_template_id", "task_instances", ["template_id"])
    op.create_index("ix_task_instances_user_id", "task_instances", ["user_id"])
    op.create_index("ix_task_instances_site_id", "task_instances", ["site_id"])


def downgrade() -> None:
    op.drop_index("ix_task_instances_site_id", table_name="task_instances")
    op.drop_index("ix_task_instances_user_id", table_name="task_instances")
    op.drop_index("ix_task_instances_template_id", table_name="task_instances")
    op.drop_table("task_instances")

    op.drop_index("ix_task_templates_audience_rule_set_id", table_name="task_templates")
    op.drop_index("ix_task_templates_task_key", table_name="task_templates")
    op.drop_table("task_templates")
