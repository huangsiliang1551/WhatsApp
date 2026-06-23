"""Enhance audit_logs table with ip_address, user_agent, action_type fields.

Revision ID: 20260617_0082
Revises: 20260617_0081
Create Date: 2026-06-17 06:50:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0082"
down_revision: str | None = "20260617_0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(500), nullable=True))
    op.add_column("audit_logs", sa.Column("action_type", sa.String(32), nullable=True))
    op.create_index("ix_audit_logs_action_type", "audit_logs", ["action_type"])
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_type", table_name="audit_logs")
    op.drop_column("audit_logs", "action_type")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "ip_address")
