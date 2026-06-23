"""Merge 20260619_0100 and 20260619_0101 branches.

Revision ID: 20260619_0102
Revises: 20260619_0100, 20260619_0101
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0102"
down_revision: str | None = ("20260619_0100", "20260619_0101")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
