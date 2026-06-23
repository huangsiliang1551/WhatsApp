"""Merge H5 template migration heads.

Revision ID: 20260623_0108
Revises: 20260618_0101, 20260623_0107
Create Date: 2026-06-23 02:30:00
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260623_0108"
down_revision: str | Sequence[str] | None = ("20260618_0101", "20260623_0107")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
