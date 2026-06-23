"""Add persistent review metadata to member verification requests.

Revision ID: 20260612_0064
Revises: 20260612_0063
Create Date: 2026-06-12 11:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260612_0064"
down_revision: str | None = "20260612_0063"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("member_verification_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reviewer_actor_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("member_verification_requests", schema=None) as batch_op:
        batch_op.drop_column("reviewer_actor_id")
        batch_op.drop_column("review_note")
